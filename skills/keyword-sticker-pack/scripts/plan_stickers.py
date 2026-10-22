#!/usr/bin/env python3
"""Planifie pops d'emojis/bulles synchronisés sur des mots horodatés.

Entrée JSON : [{"t": 11.5, "word": "clé", "dur": 1.1}, ...]
Sorties : plan JSON (chemins PNG + fenêtres + positions) ou commande FFmpeg.
Styles : pop (coin), bubble (cercle près du visage), center (objet géant).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# dictionnaire objet (codepoint Twemoji) — extensible
OBJECTS = {
    "clé": "1f511", "cles": "1f511", "cle": "1f511", "cerveau": "1f9e0",
    "potion": "1f9ea", "formule": "1f9ea", "ampoule": "1f4a1", "idee": "1f4a1",
    "argent": "1f4b0", "dollars": "1f4b5", "feu": "1f525", "maison": "1f3e0",
    "banque": "1f3e6", "carte": "1f4b3", "dettes": "1f4c9", "sifflet": "1f4ef",
    "poignee": "1f91d", "message": "1f4ac", "horloge": "23f0", "alerte": "26a0",
    "eclair": "26a1", "target": "1f3af", "bouclier": "6e1e", "clef": "1f5dd",
}

STYLES = {
    "pop":     dict(w=216, x="main_w-overlay_w-70", y=160),
    "bubble":  dict(w=260, x="FACE_X-130", y="main_h*0.34"),
    "center":  dict(w=320, x="(main_w-overlay_w)/2", y="main_h*0.22"),
}


def pick(word: str, fallback: str = "1f4a1") -> str:
    w = word.strip().lower()
    if w in OBJECTS:
        return OBJECTS[w]
    for key, cp in OBJECTS.items():
        if key in w:
            return cp
    return fallback


def build(events, style, size, twemoji_dir, face_x):
    st = dict(STYLES[style])
    if size:
        st["w"] = size
    x = st["x"].replace("FACE_X", str(face_x or 540))
    plan = []
    for ev in events:
        t = float(ev["t"])
        dur = float(ev.get("dur", 1.1))
        cp = ev.get("cp") or pick(ev.get("word", ""))
        png = Path(twemoji_dir) / f"{cp}.png"
        plan.append({
            "t": t, "dur": dur, "word": ev.get("word", ""),
            "src": str(png), "exists": png.is_file(),
            "width": st["w"], "x": x, "y": st["y"],
            "enable": f"between(t\\,{t:.3f}\\,{t + dur:.3f})",
        })
    return plan


def print_cmd(plan):
    ins, fcs, labels = [], [], "[0:v]"
    for i, p in enumerate(plan):
        ins += ["-i", p["src"]]
        lab = "[vout]" if i == len(plan) - 1 else f"[s{i}]"
        fcs.append(f"[{i + 1}:v]scale=w={p['width']}:h=-1:eval=frame,"
                   f"setsar=1,format=rgba[p{i}]")
        fcs.append(f"{labels}[p{i}]overlay=x={p['x']}:y={p['y']}:"
                   f"enable='{p['enable']}'{lab}")
        labels = f"[s{i}]"
    cmd = ["ffmpeg", "-i", "IN.mp4", *ins, "-filter_complex", ";".join(fcs),
           "-map", "[vout]", "-map", "0:a", "-c:a", "copy", "OUT.mp4"]
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("events")
    ap.add_argument("--style", choices=sorted(STYLES), default="pop")
    ap.add_argument("--size", type=int, default=0)
    ap.add_argument("--face-x", type=int, default=540)
    ap.add_argument("--twemoji-dir", default=str(ROOT / "twemoji"))
    ap.add_argument("-o", help="plan JSON")
    ap.add_argument("--print-cmd", action="store_true")
    a = ap.parse_args()
    events = json.loads(Path(a.events).read_text(encoding="utf-8"))
    plan = build(events, a.style, a.size, a.twemoji_dir, a.face_x)
    if a.o:
        Path(a.o).write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"plan : {a.o} ({len(plan)} pops)")
    else:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    missing = [p for p in plan if not p["exists"]]
    for m in missing:
        print(f"PNG absent (gh api jdecked/twemoji …/{m['src'].split('/')[-1]}) : {m['src']}",
              file=sys.stderr)
    if a.print_cmd:
        print_cmd(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
