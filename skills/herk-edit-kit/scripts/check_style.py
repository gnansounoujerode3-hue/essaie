#!/usr/bin/env python3
"""Vérifie l'intégrité de style-library/registry.json (styles référencés = dossiers existants)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "style-library" / "registry.json"


def main() -> int:
    if not REG.is_file():
        print(f"registry.json absent : {REG}")
        return 1
    data = json.loads(REG.read_text(encoding="utf-8"))
    styles = data.get("styles", data) if isinstance(data, dict) else data
    if isinstance(styles, dict):
        entries = list(styles.keys())
    else:
        entries = [s.get("id") or s.get("name", "?") for s in styles]
    missing = []
    for entry in entries:
        folder = ROOT / "style-library" / str(entry)
        if not folder.is_dir():
            # les dossiers sont numérotés : 01-vox-explainer…
            hits = list((ROOT / "style-library").glob(f"*{entry}*"))
            if not hits:
                missing.append(entry)
    ok = len(entries) - len(missing)
    print(f"styles : {ok}/{len(entries)} présents")
    for m in missing:
        print(f"  manquant : {m}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
