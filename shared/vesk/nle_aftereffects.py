"""Génération de scripts After Effects (JSX) : comps, placement, marqueurs, sous-titres."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from .common import SkillError
from .nle_premiere import normalize_markers


def _js(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _ae_text(value: str) -> str:
    cleaned = re.sub(r"\{[^}]*\}", "", value).replace("\\N", "\n").strip()
    return _js(cleaned.replace("\n", "\r"))


def build_ae_jsx(
    plan: dict[str, Any],
    *,
    comp_name: str | None = None,
    markers: Sequence[dict[str, Any]] = (),
    captions: Sequence[dict[str, Any]] = (),
    caption_style: dict[str, Any] | None = None,
    beat_bpm: float | None = None,
    save_path: str | None = None,
) -> str:
    name = comp_name or plan["name"]
    width, height = plan["width"], plan["height"]
    fps = plan["fps"]
    duration = max(1.0, plan["duration"] + 0.5)
    style = caption_style or {}
    font = style.get("font", "Montserrat-ExtraBold")
    font_size = float(style.get("font_size", 90)) * height / 1920.0
    color = _hex_to_rgb(style.get("primary", "#FFFFFF"))
    highlight = _hex_to_rgb(style.get("highlight_color", "#FFD400"))

    lines = [
        "// Généré par VESK — after-effects-scripting",
        "// Exécution : After Effects → Fichier → Scripts → Exécuter un fichier de script",
        "(function () {",
        "    app.beginUndoGroup(\"VESK assembly\");",
        "    var project = app.project;",
        "    if (!project) { project = app.newProject(); }",
        f"    var compName = {_js(name)};",
        "    var comp = null;",
        "    for (var i = 1; i <= project.numItems; i++) {",
        "        if (project.item(i) instanceof CompItem && project.item(i).name === compName) {",
        "            comp = project.item(i); break;",
        "        }",
        "    }",
        "    if (!comp) {",
        f"        comp = project.items.addComp(compName, {width}, {height}, 1.0, {duration:.3f}, {fps:.6f});",
        "    }",
        "    comp.openInViewer();",
        "    function findFootage(path) {",
        "        var file = new File(path);",
        "        var base = file.name;",
        "        for (var i = 1; i <= project.numItems; i++) {",
        "            var item = project.item(i);",
        "            if (item instanceof FootageItem && item.name === base) { return item; }",
        "        }",
        "        var opts = new ImportOptions(file);",
        "        return project.importFile(opts);",
        "    }",
        "    var videoTrack = 1;",
    ]
    for clip in plan["clips"]:
        lines += [
            "    (function () {",
            f"        var footage = findFootage({_js(str(Path(clip['source']).expanduser().resolve()))});",
            "        if (!footage) { return; }",
            "        var layer = comp.layers.add(footage);",
            f"        layer.startTime = {clip['start']:.3f} - {clip['in']:.3f};",
            f"        layer.inPoint = {clip['start']:.3f};",
            f"        layer.outPoint = {clip['start'] + clip['duration']:.3f};",
            f"        layer.name = {_js(clip['name'])};",
            "    })();",
        ]
    all_markers = list(markers) + [m for clip in plan["clips"] for m in clip.get("markers", [])]
    for marker in normalize_markers(all_markers):
        lines += [
            "    (function () {",
            f"        var m = new MarkerValue({_js(marker['name'])});",
            f"        m.comment = {_js(marker['note'])};",
            f"        comp.markerProperty.setValueAtTime({marker['time']:.3f}, m);",
            "    })();",
        ]
    if captions:
        lines += [
            "    // Sous-titres animés (texte par mot)",
            "    var captionLayer = null;",
            "    function makeCaptionLayer() {",
            f"        var textLayer = comp.layers.addText(\"\");",
            "        textLayer.name = \"CAPTIONS\";",
            "        textLayer.property(\"Anchor Point\").expression = " +
            "\"[thisLayer.sourceRectAtTime().width/2, thisLayer.sourceRectAtTime().height/2]\";",
            f"        textLayer.property(\"Position\").setValue([{width / 2}, {height * 0.78}]);",
            "        var sourceText = textLayer.property(\"Source Text\");",
            "        var doc = sourceText.value;",
            f"        try {{ doc.font = {_js(font)}; }} catch (e) {{}}",
            f"        doc.fontSize = {font_size:.1f};",
            f"        doc.fillColor = [{color[0]}, {color[1]}, {color[2]}];",
            "        doc.applyFill = true;",
            "        doc.applyStroke = false;",
            "        doc.justification = ParagraphJustification.CENTER_JUSTIFY;",
            "        sourceText.setValue(doc);",
            "        return textLayer;",
            "    }",
        ]
        for index, event in enumerate(captions):
            text = re.sub(r"\{[^}]*\}", "", str(event["text"])).replace("\\N", "\n")
            if index % 40 == 0:
                lines.append("    captionLayer = makeCaptionLayer();")
            lines += [
                "    (function () {",
                f"        var keyed = captionLayer.property(\"Source Text\").addKey({event['start']:.3f});",
                f"        keyed.setValue({_ae_text(text)});",
                f"        var next = captionLayer.property(\"Source Text\").addKey({event['end']:.3f});",
                "        next.setValue(\"\");",
                "    })();",
            ]
    if beat_bpm:
        period = 60.0 / max(1.0, beat_bpm)
        lines += [
            "    // Pulse rythmique piloté par le BPM",
            "    var pulseLayer = comp.layers.addNull();",
            "    pulseLayer.name = \"BEAT PULSE\";",
            f"    var period = {period:.4f};",
            "    pulseLayer.property(\"Scale\").expression = " +
            "\"var bpmPeriod = \" + period + \";\" +",
            "        \"var phase = (time % bpmPeriod) / bpmPeriod;\" +",
            "        \"var bump = Math.max(0, 1 - phase * 6);\" +",
            "        \"[100 + bump * 6, 100 + bump * 6]\";",
            "    pulseLayer.enabled = false;",
        ]
    lines += [
        "    comp.workAreaDuration = " + f"{duration:.3f}" + ";",
    ]
    if save_path:
        lines += [
            f"    project.save(new File({_js(save_path)}));",
        ]
    lines += [
        "    app.endUndoGroup();",
        "    alert(\"VESK : comp \" + comp.name + \" prête (\" + comp.numLayers + \" calques).\");",
        "})();",
        "",
    ]
    return "\n".join(lines)


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    raw = str(value).lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return 1.0, 1.0, 1.0
    return (int(raw[0:2], 16) / 255.0, int(raw[2:4], 16) / 255.0, int(raw[4:6], 16) / 255.0)


def beat_reactive_expression(bpm: float, *, axis: str = "scale",
                             strength: float = 6.0, decay: float = 6.0) -> str:
    """Expression AE prête à coller : pulsation sur les temps forts."""
    axis = axis.lower()
    value = "[100 + bump * {s}, 100 + bump * {s}]".format(s=strength) if axis == "scale" \
        else "[value[0], value[1] - bump * {s}]".format(s=strength)
    return (
        f"var bpmPeriod = {60.0 / max(1.0, bpm):.4f};\n"
        "var phase = (time % bpmPeriod) / bpmPeriod;\n"
        f"var bump = Math.max(0, 1 - phase * {decay:g});\n"
        f"{value};"
    )


def text_layer_jsx(text: str, *, name: str = "TEXTE", start: float = 0.0,
                   duration: float = 3.0, font_size: float = 120,
                   color: str = "#FFFFFF", x: int = 540, y: int = 960) -> str:
    rgb = _hex_to_rgb(color)
    return "\n".join([
        "(function () {",
        "    var comp = app.project.activeItem;",
        f"    var layer = comp.layers.addText({_ae_text(text)});",
        f"    layer.name = {_js(name)};",
        f"    layer.inPoint = {start:.3f}; layer.outPoint = {start + duration:.3f};",
        "    var sourceText = layer.property(\"Source Text\");",
        "    var doc = sourceText.value;",
        f"    doc.fontSize = {font_size:.1f};",
        f"    doc.fillColor = [{rgb[0]}, {rgb[1]}, {rgb[2]}];",
        "    doc.applyFill = true;",
        "    doc.justification = ParagraphJustification.CENTER_JUSTIFY;",
        "    sourceText.setValue(doc);",
        "    layer.property(\"Anchor Point\").expression = " +
        "\"[thisLayer.sourceRectAtTime().width/2, thisLayer.sourceRectAtTime().height/2]\";",
        f"    layer.property(\"Position\").setValue([{x}, {y}]);",
        "})();",
        "",
    ])


def load_captions(path: str | Path) -> list[dict[str, Any]]:
    import json as _json

    data = _json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("events") or data.get("captions") or []
    if not isinstance(data, list):
        raise SkillError("Fichier de captions invalide (liste d'événements attendue).")
    return data
