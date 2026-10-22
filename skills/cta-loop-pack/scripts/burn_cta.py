#!/usr/bin/env python3
"""Génère un .ass de CTA à partir de data/cta_templates.ass (motifs, horodatages).

--list                      : liste les motifs (ligne commençant par « # id »)
--times id=sec[,id=sec…]    : pose chaque motif à sa seconde
-o out.ass                  : écrit le fichier final
--print-cmd                 : affiche la commande FFmpeg d'incrustation
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "data" / "cta_templates.ass"

# id -> numéro de Dialogue dans le bloc [Events] (0-indexé, ordre du fichier)
IDS = {"follow": 1, "subscribe": 0, "comment": 2, "question": 3, "loop": 5}


def timecode(sec: float) -> str:
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def split_sections(text: str):
    head, events, in_events = [], [], False
    for line in text.splitlines():
        if line.startswith("[Events]"):
            in_events = True
            head.append(line)
            continue
        if in_events and line.startswith("Dialogue:"):
            events.append(line)
        elif in_events:
            head.append(line)
        else:
            head.append(line)
    return head, events


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--times", help="follow=55.5,comment=57")
    ap.add_argument("-o", default="cta.ass")
    ap.add_argument("--print-cmd", action="store_true")
    a = ap.parse_args()

    if not TPL.is_file():
        print(f"templates absents : {TPL}", file=sys.stderr)
        return 2
    text = TPL.read_text(encoding="utf-8")

    if a.list:
        for cid, idx in IDS.items():
            print(f"{cid:12s} motif n°{idx}")
        return 0

    picked = []
    if a.times:
        for item in a.times.split(","):
            cid, _, sec = item.partition("=")
            cid = cid.strip()
            if cid not in IDS:
                print(f"motif inconnu : {cid} (voir --list)", file=sys.stderr)
                return 1
            picked.append((cid, float(sec)))

    head, events = split_sections(text)
    out_events = []
    for cid, sec in picked:
        src = events[IDS[cid]]
        parts = src.split(",", 9)
        parts[1] = timecode(sec)
        # durée de la fenêtre d'origine
        oh, om, os_ = parts[2].split(":")
        dur = int(oh) * 3600 + int(om) * 60 + float(os_)
        parts[2] = timecode(sec + dur)
        out_events.append(",".join(parts))

    body = "\n".join(head + out_events) + "\n"
    Path(a.o).write_text(body, encoding="utf-8")
    print(f"écrit : {a.o} ({len(out_events)} CTA)")

    if a.print_cmd:
        print(f'ffmpeg -i IN.mp4 -vf "ass={a.o}:fontsdir=/usr/share/fonts/truetype/dejavu" '
              f'-c:v libx264 -crf 18 -c:a copy OUT.mp4')
    return 0


if __name__ == "__main__":
    sys.exit(main())
