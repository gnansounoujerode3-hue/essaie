"""Génération de scripts Python pour DaVinci Resolve (import timeline, markers, render, LUT)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from .nle_premiere import normalize_markers


def _py(value: Any) -> str:
    return repr(value)


def _frames(seconds: float, fps: float) -> int:
    return int(round(max(0.0, seconds) * fps))


def build_resolve_script(
    plan: dict[str, Any],
    *,
    timeline_name: str | None = None,
    fcpxml_path: str | None = None,
    markers: Sequence[dict[str, Any]] = (),
    render: dict[str, Any] | None = None,
    lut_path: str | None = None,
    project_fps: float | None = None,
) -> str:
    """Script exécutable dans Resolve (menu Workspace → Scripts)."""
    name = timeline_name or plan["name"]
    fps = float(project_fps or plan["fps"])
    fps_setting = str(int(round(fps))) if abs(fps - round(fps)) < 0.02 else f"{fps:.3f}"
    marker_rows = normalize_markers(list(markers) + [m for c in plan["clips"] for m in c.get("markers", [])])
    render_settings = render or {}
    marker_payload = [
        {**marker, "frame": _frames(marker["time"], fps),
         "duration_frames": _frames(marker["duration"], fps)}
        for marker in marker_rows
    ]
    lines = [
        '"""Généré par VESK — davinci-resolve-python-api.',
        "",
        "Exécution :",
        "  1. DaVinci Resolve ouvert avec un projet.",
        "  2. Workspace → Scripts → (ce fichier doit être dans le dossier Scripts)",
        "     ou Console → exec(open(r'CE_FICHIER.py', encoding='utf-8').read())",
        '"""',
        "import os",
        "import sys",
        "",
        "try:",
        "    import DaVinciResolveScript as dvr",
        "except ImportError:",
        "    # chemins usuels selon l'OS",
        "    candidates = [",
        "        '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules',",
        "        '/opt/resolve/Developer/Scripting/Modules',",
        "        os.path.expandvars(r'%PROGRAMDATA%\\\\Blackmagic Design\\\\DaVinci Resolve\\\\Support\\\\Developer\\\\Scripting\\\\Modules'),",
        "    ]",
        "    for path in candidates:",
        "        if path and os.path.isdir(path) and path not in sys.path:",
        "            sys.path.append(path)",
        "    import DaVinciResolveScript as dvr",
        "",
        "resolve = dvr.scriptapp('Resolve')",
        "if resolve is None:",
        "    raise RuntimeError('DaVinci Resolve doit être lancé avant ce script.')",
        "project_manager = resolve.GetProjectManager()",
        "project = project_manager.GetCurrentProject()",
        "if project is None:",
        "    raise RuntimeError('Ouvre un projet Resolve avant de lancer le script.')",
        "media_pool = project.GetMediaPool()",
        "if media_pool is None:",
        "    raise RuntimeError('Media Pool indisponible.')",
        "",
        f"TIMELINE_NAME = {_py(name)}",
        f"FPS = {fps!r}",
        "",
        "# 1) Réglage de la fréquence du projet",
        f"project.SetSetting('timelineFrameRate', {_py(fps_setting)})",
        "project.SetSetting('timelineResolutionWidth', " + _py(str(plan["width"])) + ")",
        "project.SetSetting('timelineResolutionHeight', " + _py(str(plan["height"])) + ")",
        "",
    ]
    if fcpxml_path:
        lines += [
            "# 2) Import de la timeline depuis le FCPXML VESK (placement exact des clips)",
            f"FCPXML = {_py(str(Path(fcpxml_path).expanduser()))}",
            "timeline = None",
            "if os.path.exists(FCPXML):",
            "    timeline = media_pool.ImportTimelineFromFile(FCPXML, {",
            "        'timelineName': TIMELINE_NAME,",
            "        'importSourceClips': True,",
            "    })",
            "else:",
            "    print('FCPXML introuvable :', FCPXML)",
        ]
    else:
        sources = []
        for clip in plan["clips"]:
            path = clip["source"]
            if path not in sources:
                sources.append(path)
        lines += [
            "# 2) Append séquentiel des clips (sans FCPXML, les positions exactes ne sont pas garanties)",
            f"SOURCES = {_py(sources)}",
            "items = media_pool.ImportMedia(SOURCES) or []",
            "by_name = {os.path.basename(i.GetClipProperty('File Path')): i for i in items}",
            "media_pool.SetCurrentFolder(media_pool.GetRootFolder())",
            "timeline = media_pool.CreateEmptyTimeline(TIMELINE_NAME)",
            "if timeline is None:",
            "    timeline = project.GetCurrentTimeline()",
            "clip_infos = []",
        ]
        for clip in plan["clips"]:
            lines += [
                "clip_infos.append({",
                f"    'name': {_py(clip['name'])},",
                f"    'startFrame': {_frames(clip['in'], fps)},",
                f"    'endFrame': {_frames(clip['out'], fps)},",
                f"    'trackIndex': 1,",
                "    'mediaType': 1,",
                "})",
            ]
        lines += [
            "pool_items = []",
            "for info, clip in zip(clip_infos, " + _py([c["source"] for c in plan["clips"]]) + "):",
            "    item = by_name.get(os.path.basename(clip))",
            "    if item is None:",
            "        print('Média manquant :', clip)",
            "        continue",
            "    pool_items.append({",
            "        'mediaPoolItem': item,",
            "        'startFrame': info['startFrame'],",
            "        'endFrame': info['endFrame'],",
            "        'trackIndex': 1,",
            "        'mediaType': 1,",
            "    })",
            "if pool_items:",
            "    media_pool.AppendToTimeline(pool_items)",
        ]
    lines += [
        "",
        "if timeline is None:",
        "    raise RuntimeError('Création de timeline impossible — vérifie les médias et le FCPXML.')",
        "project.SetCurrentTimeline(timeline)",
        "",
        "# 3) Marqueurs de montage",
        f"MARKERS = {_py(marker_payload)}",
        "for marker in MARKERS:",
        "    timeline.AddMarker(marker['frame'], marker.get('color', 'Blue'),",
        "                       marker['name'], marker.get('note', ''), marker['duration_frames'])",
        "",
    ]
    if lut_path:
        lines += [
            "# 4) LUT appliquée à tous les clips de la piste 1",
            f"LUT = {_py(str(Path(lut_path).expanduser()))}",
            "if os.path.exists(LUT):",
            "    for item in timeline.GetItemListInTrack('video', 1) or []:",
            "        try:",
            "            item.SetLUT(1, LUT)",
            "        except Exception as exc:",
            "            print('LUT impossible sur', item.GetName(), exc)",
            "else:",
            "    print('LUT introuvable :', LUT)",
            "",
        ]
    if render_settings:
        out_dir = str(render_settings.get("output_dir") or "").replace("\\", "/")
        lines += [
            "# 5) Rendu",
            f"RENDER_DIR = {_py(out_dir)}",
            "os.makedirs(RENDER_DIR, exist_ok=True)",
            "settings = {",
            "    'SelectAll': True,",
            "    'TargetDir': RENDER_DIR,",
            f"    'CustomName': {_py(str(render_settings.get('name') or name))},",
            "}",
        ]
        if render_settings.get("preset"):
            lines += [
                f"preset = {_py(str(render_settings['preset']))}",
                "if os.path.exists(preset):",
                "    project.LoadRenderPreset(preset)",
            ]
        if render_settings.get("format"):
            lines += [f"settings['TargetDir'] = RENDER_DIR"]
            lines += [f"project.SetCurrentRenderFormatAndCodec({_py(render_settings['format'])}, "
                      f"{_py(render_settings.get('codec', 'H264'))})"]
        lines += [
            "project.SetRenderSettings(settings)",
            "job_id = project.AddRenderJob()",
            "if job_id:",
            "    project.StartRendering([job_id])",
            "    print('Rendu lancé :', job_id)",
            "else:",
            "    print('Ajout du render job impossible.')",
            "",
        ]
    lines += [
        "print('VESK : timeline prête →', timeline.GetName())",
        "",
    ]
    return "\n".join(lines)


def write_resolve_script(path: str | Path, content: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def build_color_script(lut_path: str | None = None, *, contrast: float | None = None,
                       saturation: float | None = None,
                       temperature: float | None = None,
                       slope: tuple[float, float, float] | None = None,
                       offset: tuple[float, float, float] | None = None) -> str:
    """Script de color grading global (LUT + CDL) sur la timeline active."""
    c = float(contrast) if contrast is not None else 1.0
    s = float(saturation) if saturation is not None else 1.0
    t = float(temperature) if temperature is not None else 0.0
    r_slope = (slope[0] if slope else 1.0) * c * (1.0 + 0.12 * t)
    g_slope = (slope[1] if slope else 1.0) * c
    b_slope = (slope[2] if slope else 1.0) * c * (1.0 - 0.12 * t)
    off = offset or (0.0, 0.0, 0.0)
    lines = [
        '"""Color grading VESK — applique une LUT et un CDL sur la timeline active."""',
        "import os",
        "import DaVinciResolveScript as dvr",
        "",
        "resolve = dvr.scriptapp('Resolve')",
        "project = resolve.GetProjectManager().GetCurrentProject()",
        "timeline = project.GetCurrentTimeline()",
        "if timeline is None:",
        "    raise RuntimeError('Aucune timeline active.')",
        "items = timeline.GetItemListInTrack('video', 1) or []",
        "",
    ]
    if lut_path:
        lines += [
            f"LUT = {_py(str(Path(lut_path).expanduser()))}",
            "for item in items:",
            "    if os.path.exists(LUT):",
            "        try:",
            "            item.SetLUT(1, LUT)",
            "        except Exception as exc:",
            "            print('LUT impossible :', exc)",
            "    else:",
            "        print('LUT introuvable :', LUT)",
            "",
        ]
    lines += [
        "# CDL (node 1) — valeurs générées depuis les paramètres VESK",
        f"CDL = {{",
        f"    'NodeIndex': '1',",
        f"    'Slope': {_py(f'{r_slope:.3f} {g_slope:.3f} {b_slope:.3f}')},",
        f"    'Offset': {_py(f'{off[0]:.4f} {off[1]:.4f} {off[2]:.4f}')},",
        "    'Power': '1.0 1.0 1.0',",
        f"    'Sat': {_py(f'{s:.3f}')},",
        "}",
        "for item in items:",
        "    try:",
        "        item.SetCDL(CDL)",
        "    except Exception as exc:",
        "        print('CDL non supporté sur ce clip :', exc)",
        "",
        "print('Color grading VESK terminé sur', len(items), 'clip(s).')",
        "",
    ]
    return "\n".join(lines)


def describe_workflow() -> str:
    return (
        "Workflow Resolve :\n"
        "  1. `build_resolve.py --plan edit.json --out-prefix resolve/job`\n"
        "  2. Copier `resolve_job.py` dans le dossier Scripts de Resolve\n"
        "     (macOS : ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit)\n"
        "  3. Ouvrir Resolve, charger le projet, puis Workspace → Scripts → resolve_job\n"
        "  4. Le script importe la timeline FCPXML, ajoute les marqueurs, la LUT et lance le rendu.\n"
    )
