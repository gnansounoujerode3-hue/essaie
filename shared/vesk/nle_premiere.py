"""Plans de montage → FCPXML / XMEML / EDL / marqueurs, et scripts Premiere Pro (JSX)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from .common import SkillError, fmt_timecode, read_json, slugify, write_json
from .ffmpeg import media_info


# --------------------------------------------------------------------------- plan


def normalize_plan(data: Any, *, default_source: str | None = None,
                   fps: float | None = None, width: int | None = None,
                   height: int | None = None, name: str | None = None) -> dict[str, Any]:
    if isinstance(data, list):
        data = {"clips": data}
    if not isinstance(data, dict):
        raise SkillError("Plan de montage invalide.")
    raw_clips = data.get("clips") or data.get("segments") or data.get("plan")
    if not raw_clips:
        raise SkillError("Le plan ne contient aucun clip ('clips' vide).")
    plan_fps = float(fps or data.get("fps") or 30.0)
    clips = []
    cursor = 0.0
    for index, raw in enumerate(raw_clips, start=1):
        if not isinstance(raw, dict):
            raise SkillError(f"Clip #{index} invalide.")
        source = raw.get("source") or raw.get("path") or raw.get("file") or default_source
        if not source:
            raise SkillError(f"Clip #{index} sans source (--media ou clé 'source').")
        if "in" in raw or "out" in raw:
            src_in = float(raw.get("in", 0.0))
            src_out = float(raw.get("out", src_in + float(raw.get("duration", 3.0))))
        else:
            src_in = float(raw.get("start", 0.0))
            src_out = float(raw.get("end", src_in + float(raw.get("duration", 3.0))))
        if src_out <= src_in:
            raise SkillError(f"Clip #{index} : out <= in.")
        timeline_start = raw.get("timeline_start")
        if timeline_start is None:
            timeline_start = cursor
        clips.append({
            "index": index,
            "name": raw.get("name") or Path(str(source)).stem,
            "source": str(source),
            "in": round(src_in, 3),
            "out": round(src_out, 3),
            "start": round(float(timeline_start), 3),
            "duration": round(src_out - src_in, 3),
            "source_duration": float(raw.get("source_duration") or 0.0),
            "width": int(raw.get("width") or 0),
            "height": int(raw.get("height") or 0),
            "has_audio": bool(raw.get("has_audio", True)),
            "markers": raw.get("markers", []),
        })
        cursor = max(cursor, clips[-1]["start"] + clips[-1]["duration"])
    # complète les métadonnées quand les fichiers sont accessibles
    for clip in clips:
        path = Path(clip["source"])
        if not path.exists():
            continue
        try:
            meta = media_info(path)
        except SkillError:
            continue
        clip["source_duration"] = clip["source_duration"] or meta["duration"]
        clip["width"] = clip["width"] or meta["width"] or int(data.get("width") or 1920)
        clip["height"] = clip["height"] or meta["height"] or int(data.get("height") or 1080)
        clip["has_audio"] = bool(meta["has_audio"])
    width = int(width or data.get("width") or 1080)
    height = int(height or data.get("height") or 1920)
    for clip in clips:
        if not clip["source_duration"]:
            clip["source_duration"] = max(clip["out"], clip["in"] + clip["duration"])
        if not clip["width"]:
            clip["width"] = width
        if not clip["height"]:
            clip["height"] = height
    return {
        "name": name or data.get("name") or "VESK assembly",
        "fps": plan_fps,
        "width": width,
        "height": height,
        "clips": clips,
        "markers": normalize_markers(data.get("markers") or []),
        "duration": round(max((c["start"] + c["duration"] for c in clips), default=0.0), 3),
    }


def plan_from_highlights(data: dict[str, Any], source: str, **kwargs: Any) -> dict[str, Any]:
    clips = [
        {"source": source, "in": clip["start"], "out": clip["end"],
         "name": f"{Path(source).stem} #{clip.get('rank', index + 1)}"}
        for index, clip in enumerate(data.get("clips", []))
    ]
    return normalize_plan({"clips": clips}, **kwargs)


# --------------------------------------------------------------------------- helpers


def _fps_int(fps: float) -> int:
    return max(1, int(round(fps)))


def _frames(seconds: float, fps: float) -> int:
    return int(round(max(0.0, seconds) * fps))


def _rfc2822_fps(fps: float) -> str:
    if abs(fps - round(fps)) < 0.01:
        return f"1/{int(round(fps))}s"
    if abs(fps - 29.97) < 0.02:
        return "1001/30000s"
    if abs(fps - 23.976) < 0.02:
        return "1001/24000s"
    if abs(fps - 59.94) < 0.02:
        return "1001/60000s"
    return f"{int(round(1000 / fps))}/1000s"


def _fcpxml_time(seconds: float, fps: float) -> str:
    fps_int = _fps_int(fps)
    if abs(fps - 29.97) < 0.02 or abs(fps - 59.94) < 0.02 or abs(fps - 23.976) < 0.02:
        den = 30000 if abs(fps - 29.97) < 0.02 else (60000 if abs(fps - 59.94) < 0.02 else 24000)
        return f"{int(round(seconds * den))}/{den}s"
    return f"{_frames(seconds, fps_int)}/{fps_int}s"


def _format_name(width: int, height: int, fps: float) -> str:
    base = {(1920, 1080): "FFVideoFormat1080p", (1080, 1920): "FFVideoFormat1080p",
            (3840, 2160): "FFVideoFormat2160p", (2160, 3840): "FFVideoFormat2160p",
            (1080, 1080): "FFVideoFormat1080p", (1280, 720): "FFVideoFormat720p"}
    prefix = base.get((width, height))
    if not prefix:
        return "FFVideoFormatRateUndefined"
    if abs(fps - 29.97) < 0.02:
        return prefix + "2997"
    if abs(fps - 23.976) < 0.02:
        return prefix + "2398"
    if abs(fps - 59.94) < 0.02:
        return prefix + "5994"
    return prefix + str(_fps_int(fps))


def file_url(path: str) -> str:
    """URL de fichier locale, valide sur POSIX comme sur Windows."""
    resolved = Path(path).expanduser()
    try:
        resolved = resolved.resolve()
    except OSError:
        pass
    text = resolved.as_posix()
    if re.match(r"^[A-Za-z]:", text):  # C:/… → /C:/…
        text = "/" + text
    return "file://localhost" + quote(text, safe="/:")


def _safe_text(value: Any) -> str:
    return escape(str(value))


# --------------------------------------------------------------------------- FCPXML


def to_fcpxml(plan: dict[str, Any], *, project_name: str | None = None) -> str:
    fps = plan["fps"]
    name = project_name or plan["name"]
    width, height = plan["width"], plan["height"]
    rid = 1
    assets = []
    asset_ids: dict[str, str] = {}
    for clip in plan["clips"]:
        source = clip["source"]
        if source in asset_ids:
            continue
        asset_id = f"r{rid}"; rid += 1
        asset_ids[source] = asset_id
        audio = ' audioSources="1" audioChannels="2"' if clip["has_audio"] else ""
        assets.append(
            f'    <asset id="{asset_id}" name={quoteattr(Path(source).name)} '
            f'start="0s" duration="{_fcpxml_time(clip["source_duration"], fps)}" '
            f'hasVideo="1"{audio} format="r1">\n'
            f'      <media-rep kind="original-media" src="{_safe_text(file_url(source))}"/>\n'
            f'    </asset>'
        )
    clips_xml = []
    for clip in plan["clips"]:
        asset_id = asset_ids[clip["source"]]
        duration = _fcpxml_time(clip["duration"], fps)
        offset = _fcpxml_time(clip["start"], fps)
        start = _fcpxml_time(clip["in"], fps)
        inner = [
            f'        <video ref="{asset_id}" offset="{start}" duration="{duration}"/>',
        ]
        if clip["has_audio"]:
            inner.append(
                f'        <audio ref="{asset_id}" lane="-1" offset="{start}" duration="{duration}"/>'
            )
        clips_xml.append(
            f'      <clip name={quoteattr(clip["name"])} offset="{offset}" start="{start}" '
            f'duration="{duration}">\n' + "\n".join(inner) + "\n      </clip>"
        )
    total = _fcpxml_time(plan["duration"], fps)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE fcpxml>\n'
        '<fcpxml version="1.9">\n'
        "  <resources>\n"
        f'    <format id="r1" name="{_format_name(width, height, fps)}" '
        f'frameDuration="{_rfc2822_fps(fps)}" width="{width}" height="{height}"/>\n'
        + "\n".join(assets) + "\n"
        "  </resources>\n"
        "  <library>\n"
        "    <event name=\"VESK\">\n"
        f'      <project name={quoteattr(name)}>\n'
        f'        <sequence format="r1" duration="{total}" tcStart="0s" tcFormat="NDF">\n'
        '          <spine>\n'
        + "\n".join(clips_xml) + "\n"
        "          </spine>\n"
        "        </sequence>\n"
        "      </project>\n"
        "    </event>\n"
        "  </library>\n"
        "</fcpxml>\n"
    )


# --------------------------------------------------------------------------- XMEML


def to_xmeml(plan: dict[str, Any], *, project_name: str | None = None) -> str:
    fps = plan["fps"]
    fps_int = _fps_int(fps)
    ntsc = "TRUE" if abs(fps - fps_int) > 0.01 else "FALSE"
    name = project_name or plan["name"]
    width, height = plan["width"], plan["height"]
    file_info: dict[str, dict[str, str]] = {}
    for clip in plan["clips"]:
        source = clip["source"]
        if source in file_info:
            continue
        file_id = f"file-{len(file_info) + 1}"
        media = ""
        if clip["has_audio"]:
            media = (
                "              <media>\n"
                "                <audio>\n"
                "                  <samplecharacteristics>\n"
                "                    <depth>16</depth>\n"
                "                    <samplerate>48000</samplerate>\n"
                "                  </samplecharacteristics>\n"
                "                  <channelcount>2</channelcount>\n"
                "                </audio>\n"
                "              </media>\n"
            )
        body = (
            f'          <file id="{file_id}">\n'
            f'            <name>{_safe_text(Path(source).name)}</name>\n'
            f'            <pathurl>{_safe_text(file_url(source))}</pathurl>\n'
            f'            <rate><timebase>{fps_int}</timebase><ntsc>{ntsc}</ntsc></rate>\n'
            f'            <duration>{_frames(clip["source_duration"], fps)}</duration>\n'
            f"{media}"
            "          </file>"
        )
        file_info[source] = {"id": file_id, "body": body}

    used_files: set[str] = set()
    video_items = []
    audio_items = []

    def clip_item(clip: dict[str, Any], index: int, mediatype: str) -> str:
        source = clip["source"]
        info = file_info[source]
        file_xml = info["body"] if source not in used_files else f'          <file id="{info["id"]}"/>'
        used_files.add(source)
        start = _frames(clip["start"], fps)
        end = _frames(clip["start"] + clip["duration"], fps)
        src_in = _frames(clip["in"], fps)
        src_out = _frames(clip["out"], fps)
        return (
            f'        <clipitem id="clipitem-{index}-{mediatype}">\n'
            f"          <name>{_safe_text(clip['name'])}</name>\n"
            f"          <duration>{_frames(clip['source_duration'], fps)}</duration>\n"
            f"          <rate><timebase>{fps_int}</timebase><ntsc>{ntsc}</ntsc></rate>\n"
            f"          <start>{start}</start>\n"
            f"          <end>{end}</end>\n"
            f"          <in>{src_in}</in>\n"
            f"          <out>{src_out}</out>\n"
            f"{file_xml}\n"
            f"          <sourcetrack><mediatype>{mediatype}</mediatype>"
            "<trackindex>1</trackindex></sourcetrack>\n"
            "        </clipitem>"
        )

    for index, clip in enumerate(plan["clips"], start=1):
        video_items.append(clip_item(clip, index, "video"))
    for index, clip in enumerate(plan["clips"], start=1):
        if clip["has_audio"]:
            audio_items.append(clip_item(clip, index, "audio"))
    rate_xml = f"<rate><timebase>{fps_int}</timebase><ntsc>{ntsc}</ntsc></rate>"
    audio_block = ""
    if audio_items:
        audio_block = (
            "      <audio>\n"
            "        <format>\n"
            "          <samplecharacteristics>\n"
            "            <depth>16</depth>\n"
            "            <samplerate>48000</samplerate>\n"
            "          </samplecharacteristics>\n"
            "        </format>\n"
            "        <track>\n"
            + "\n".join(audio_items) + "\n"
            "        </track>\n"
            "      </audio>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE xmeml>\n"
        '<xmeml version="5">\n'
        '  <sequence id="sequence-1">\n'
        f"    <name>{_safe_text(name)}</name>\n"
        f"    <duration>{_frames(plan['duration'], fps)}</duration>\n"
        f"    {rate_xml}\n"
        "    <media>\n"
        "      <video>\n"
        "        <format>\n"
        "          <samplecharacteristics>\n"
        f"            {rate_xml}\n"
        f"            <width>{width}</width>\n"
        f"            <height>{height}</height>\n"
        "            <anamorphic>FALSE</anamorphic>\n"
        "            <pixelaspectratio>square</pixelaspectratio>\n"
        "            <fielddominance>none</fielddominance>\n"
        "          </samplecharacteristics>\n"
        "        </format>\n"
        "        <track>\n"
        + "\n".join(video_items) + "\n"
        "        </track>\n"
        "      </video>\n"
        f"{audio_block}"
        "    </media>\n"
        "  </sequence>\n"
        "</xmeml>\n"
    )


# --------------------------------------------------------------------------- EDL / marqueurs


def _reel_name(path: str) -> str:
    stem = re.sub(r"[^A-Z0-9]", "", Path(path).stem.upper())
    return (stem or "AX")[:8].ljust(8)


def to_edl(plan: dict[str, Any], *, title: str | None = None) -> str:
    fps = plan["fps"]
    lines = [f"TITLE: {title or plan['name']}", "FCM: NON-DROP FRAME", ""]
    for index, clip in enumerate(plan["clips"], start=1):
        record_in = 3600.0 + clip["start"]
        record_out = record_in + clip["duration"]
        lines.append(
            f"{index:03d}  {_reel_name(clip['source'])} V     C        "
            f"{fmt_timecode(clip['in'], fps)} {fmt_timecode(clip['out'], fps)} "
            f"{fmt_timecode(record_in, fps)} {fmt_timecode(record_out, fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {Path(clip['source']).name}")
        lines.append(f"* COMMENT: {clip['name']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def normalize_markers(markers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for marker in markers:
        time = marker.get("time", marker.get("start"))
        if time is None:
            continue
        output.append({
            "time": round(float(time), 3),
            "name": str(marker.get("name") or marker.get("title") or "Marqueur"),
            "note": str(marker.get("note") or marker.get("description") or ""),
            "duration": round(float(marker.get("duration") or 0.0), 3),
            "color": str(marker.get("color") or "Violet"),
        })
    return sorted(output, key=lambda m: m["time"])


def markers_to_csv(markers: Sequence[dict[str, Any]], fps: float) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Marker Name", "In", "Out", "Description", "Type"])
    for marker in normalize_markers(markers):
        writer.writerow([
            marker["name"],
            fmt_timecode(marker["time"], fps),
            fmt_timecode(marker["time"] + marker["duration"], fps),
            marker["note"],
            "Comment",
        ])
    return buffer.getvalue()


# --------------------------------------------------------------------------- sorties


def write_outputs(plan: dict[str, Any], output_prefix: str | Path, *,
                  formats: Sequence[str] = ("fcpxml", "xml", "edl", "markers"),
                  markers: Sequence[dict[str, Any]] = ()) -> dict[str, str]:
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    base = prefix.with_suffix("") if prefix.suffix else prefix
    stem = base.name or slugify(plan["name"])
    outputs: dict[str, str] = {}
    for fmt in formats:
        fmt = fmt.lower()
        if fmt in {"fcpxml", "fcp"}:
            path = base.parent / f"{stem}.fcpxml"
            path.write_text(to_fcpxml(plan), encoding="utf-8")
        elif fmt in {"xml", "xmeml", "premiere"}:
            path = base.parent / f"{stem}.xml"
            path.write_text(to_xmeml(plan), encoding="utf-8")
        elif fmt == "edl":
            path = base.parent / f"{stem}.edl"
            path.write_text(to_edl(plan), encoding="utf-8")
        elif fmt in {"markers", "csv"}:
            if not markers:
                continue
            path = base.parent / f"{stem}-markers.csv"
            path.write_text(markers_to_csv(markers, plan["fps"]), encoding="utf-8")
            write_json(base.parent / f"{stem}-markers.json", normalize_markers(markers))
        else:
            raise SkillError(f"Format de sortie inconnu : {fmt}")
        outputs[fmt] = str(path)
    return outputs


# --------------------------------------------------------------------------- JSX


def _js_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def jsx_import_plan(plan: dict[str, Any], *, sequence_name: str | None = None,
                    import_markers: bool = True) -> str:
    """ExtendScript Premiere Pro : importe les rushes, crée la séquence, place les clips."""
    seq_name = sequence_name or plan["name"]
    files = []
    seen = set()
    for clip in plan["clips"]:
        if clip["source"] not in seen:
            seen.add(clip["source"])
            files.append(str(Path(clip["source"]).expanduser().resolve()))
    lines = [
        "// Généré par VESK — premiere-pro-extendscript-generator",
        "#target premierepro",
        "// Exécution : Premiere Pro → Fichier → Scripts → Exécuter un script",
        '(function () {',
        '    var project = app.project;',
        f'    var seqName = {_js_string(seq_name)};',
        f'    var files = [{", ".join(_js_string(f) for f in files)}];',
        '    var root = project.rootItem;',
        '    var imported = project.importFiles(files, true, root, false);',
        '    if (!imported) { alert("Import impossible — vérifie les chemins des rushes."); return; }',
        '    var seq = null;',
        '    for (var i = 0; i < project.sequences.numSequences; i++) {',
        '        if (project.sequences[i].name === seqName) { seq = project.sequences[i]; break; }',
        '    }',
        '    if (!seq) {',
        '        try {',
        f'            seq = project.createNewSequence(seqName, "VESK");',
        '        } catch (e) {',
        f'            alert("Crée une séquence 1080x1920 / {plan["fps"]:.2f} fps nommée " + seqName + " puis relance.");',
        '            return;',
        '        }',
        '    }',
        '    app.project.activeSequence = seq;',
        '    function findItem(name) {',
        '        for (var i = 0; i < root.children.numItems; i++) {',
        '            var item = root.children[i];',
        '            if (item.name === name) return item;',
        '            if (item.type === ProjectItemType.BIN) {',
        '                for (var j = 0; j < item.children.numItems; j++) {',
        '                    if (item.children[j].name === name) return item.children[j];',
        '                }',
        '            }',
        '        }',
        '        return null;',
        '    }',
        '    var videoTrack = seq.videoTracks[0];',
        f'    var fps = {plan["fps"]:.6f};',
    ]
    for clip in plan["clips"]:
        name = Path(clip["source"]).name
        lines += [
            '    (function () {',
            f'        var item = findItem({_js_string(name)});',
            '        if (!item) { return; }',
            f'        var start = {clip["start"]:.3f};',
            f'        var inPoint = {clip["in"]:.3f};',
            f'        var outPoint = {clip["out"]:.3f};',
            '        try {',
            '            if (videoTrack.overwriteClip) { videoTrack.overwriteClip(item, start); }',
            '            else { videoTrack.insertClip(item, start); }',
            '        } catch (e) {',
            f'            $.writeln("Placement impossible pour " + {_js_string(name)} + " : " + e);',
            '        }',
            '    })();',
        ]
    if import_markers:
        markers = [m for clip in plan["clips"] for m in clip.get("markers", [])]
        if markers:
            lines.append("    // marqueurs importés")
            for marker in normalize_markers(markers):
                lines += [
                    f'    (function () {{ var m = seq.markers.createMarker({marker["time"]:.3f});',
                    f'      m.name = {_js_string(marker["name"])};',
                    f'      m.comments = {_js_string(marker["note"])}; }})();',
                ]
    lines += [
        '    $.writeln("VESK : séquence prête — " + seq.name);',
        '})();',
        '',
    ]
    return "\n".join(lines)


def jsx_markers(markers: Sequence[dict[str, Any]], *, sequence_name: str | None = None) -> str:
    seq_guard = (
        f'var seq = null; for (var i = 0; i < project.sequences.numSequences; i++) '
        f'{{ if (project.sequences[i].name === {_js_string(sequence_name)}) '
        f'{{ seq = project.sequences[i]; break; }} }}'
        if sequence_name else
        'var seq = app.project.activeSequence;'
    )
    lines = [
        "// Marqueurs VESK pour Premiere Pro",
        "#target premierepro",
        "(function () {",
        "    var project = app.project;",
        f"    {seq_guard}",
        '    if (!seq) { alert("Aucune séquence active."); return; }',
        '    var existing = {};',
        '    for (var i = 0; i < seq.markers.numMarkers; i++) {',
        '        existing[seq.markers[i].name] = true;',
        '    }',
    ]
    for marker in normalize_markers(markers):
        lines += [
            f'    (function () {{',
            f'        var m = seq.markers.createMarker({marker["time"]:.3f});',
            f'        m.name = {_js_string(marker["name"])};',
            f'        m.comments = {_js_string(marker["note"])};',
            f'    }})();',
        ]
    lines += ['    $.writeln("Marqueurs VESK ajoutés : " + seq.markers.numMarkers);', "})();", ""]
    return "\n".join(lines)


def jsx_export(sequence_name: str, output_path: str, *, preset_path: str | None = None) -> str:
    preset_part = (
        f'app.encoder.encodeSequence(seq, {_js_string(output_path)}, '
        f'{_js_string(preset_path)}, app.encoder.ENCODE_IN_TO_OUT, 1);'
        if preset_path else
        'alert("Fournis --preset (.epr) pour exporter automatiquement.");'
    )
    return "\n".join([
        "// Export VESK — Premiere Pro",
        "#target premierepro",
        "(function () {",
        "    var project = app.project;",
        "    var seq = app.project.activeSequence;",
        f"    if (!seq || seq.name !== {_js_string(sequence_name)}) {{",
        f"        alert(\"Active la séquence \" + {_js_string(sequence_name)});",
        "        return;",
        "    }",
        f"    {preset_part}",
        "})();",
        "",
    ])


def write_jsx(path: str | Path, content: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def load_plan(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    data = read_json(path)
    return normalize_plan(data, **kwargs)


def plan_summary(plan: dict[str, Any]) -> str:
    lines = [
        f"Séquence « {plan['name']} » — {plan['width']}x{plan['height']} @ {plan['fps']:g} fps",
        f"{len(plan['clips'])} clip(s) · durée {plan['duration']:.1f}s",
        "",
    ]
    for clip in plan["clips"]:
        lines.append(
            f"  {clip['index']:02d}. {clip['start']:7.2f}s → "
            f"{clip['start'] + clip['duration']:7.2f}s  [{clip['in']:.2f}–{clip['out']:.2f}]  "
            f"{Path(clip['source']).name}"
        )
    return "\n".join(lines)
