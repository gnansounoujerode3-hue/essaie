#!/usr/bin/env python3
"""Vérifie l'environnement de rendu Remotion (node/npx/ffmpeg) et affiche les commandes du skill."""
import argparse
import shutil
import sys

REQUIRED = ("node", "npx", "ffmpeg")


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()  # --help → 0
    missing = [c for c in REQUIRED if not shutil.which(c)]
    for c in REQUIRED:
        mark = "manquant" if c in missing else "ok"
        print(f"{c:8s} {mark}")
    print("\ncommandes typiques :")
    print("  npx remotion compositions        # liste les compositions du projet")
    print("  npx remotion render out.mp4      # rendu")
    print("  npx remotion still frame.png     # image fixe")
    if missing:
        print("\nrendu impossible tant que node/npx/ffmpeg manquent ; "
              "porter la recette en FFmpeg/ASS (voir caption-hierarchy-styles).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
