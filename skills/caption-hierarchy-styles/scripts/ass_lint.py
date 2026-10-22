#!/usr/bin/env python3
"""Lint ASS : détecthe les grilles cassées avant incrustation.

Codes retour : 0 = propre, 1 = erreur(s), 2 = fichier absent.
Contrôles (P0) :
  - chemin vectoriel rendu en TEXTE (ex-bug « m -8018 0 18 … z » sous DETTES) ;
  - accolades { } déséquilibrées ;
  - événements avec > 3 retours à la ligne ou > 400 caractères ;
  - style référencé par un Dialogue mais absent des Styles.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PATH_AS_TEXT = re.compile(r"(?<![\w{])[mnlb]\s+-?\d{2,}\s+-?\d{2,}")
DIALOGUE = re.compile(r"^Dialogue:\s*([^,]*,){8}(.*)$", re.M)


def parse_styles(text: str) -> set[str]:
    return set(re.findall(r"^Style:\s*([^,]+),", text, re.M))


def parse_dialogues(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            out.append(("?", line))
            continue
        out.append((parts[3].strip(), parts[9]))
    return out


def lint(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    styles = parse_styles(text)
    errors, warns = [], []
    for style, body in parse_dialogues(text):
        visible = re.sub(r"\{[^}]*\}", "", body)
        if PATH_AS_TEXT.search(visible):
            errors.append(f"chemin vectoriel rendu en texte : « {visible.strip()[:70]} »")
        if body.count("{") != body.count("}"):
            errors.append(f"accolades déséquilibrées : {body.strip()[:70]}")
        if body.count("\n") > 3:
            errors.append(f"événement anormalement multi-lignes : {body.strip()[:50]}")
        if len(body) > 400:
            warns.append(f"événement très long ({len(body)} caractères)")
        if style != "?" and styles and style not in styles:
            warns.append(f"style introuvable : « {style} »")
    return {"file": str(path), "errors": errors, "warnings": warns,
            "ok": not errors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ass")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    path = Path(args.ass)
    if not path.is_file():
        print(f"absent : {path}", file=sys.stderr)
        return 2
    report = lint(path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for e in report["errors"]:
            print(f"ERREUR : {e}")
        for w in report["warnings"]:
            print(f"alerte : {w}")
        print("OK" if report["ok"] else f"{len(report['errors'])} erreur(s)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
