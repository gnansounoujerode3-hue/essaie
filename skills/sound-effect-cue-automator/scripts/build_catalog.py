#!/usr/bin/env python3
"""Fabrique un pack de SFX libres de droits avec les synthétiseurs FFmpeg."""

from __future__ import annotations

import sys
from pathlib import Path

for _parent in Path(__file__).resolve().parents:
    _found = False
    for _name in ("shared", "_shared"):
        if (_parent / _name / "vesk").is_dir():
            sys.path.insert(0, str(_parent / _name))
            _found = True
            break
    if _found:
        break

from vesk.cli import base_parser, main_guard  # noqa: E402
from vesk.common import human_size  # noqa: E402
from vesk.sfx import SYNTH, generate_catalog, load_catalog  # noqa: E402


def run() -> int:
    parser = base_parser(
        "Génère les WAV du catalogue SFX (whoosh, pop, braam, riser…).",
        epilog="Exemples :\n"
               "  build_catalog.py --generate --out ./sfx\n"
               "  build_catalog.py --generate --force --out ./sfx\n"
               "  build_catalog.py --list",
    )
    parser.add_argument("--out", "-o", default="sfx", help="Dossier des WAV")
    parser.add_argument("--generate", action="store_true", help="Crée les fichiers manquants")
    parser.add_argument("--force", action="store_true", help="Écrase les fichiers existants")
    parser.add_argument("--catalog", help="Catalogue JSON alternatif")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    if args.list or not args.generate:
        print(f"{'ID':<14} {'GAIN':>6}  FICHIER")
        for effect in catalog["effects"]:
            print(f"{effect['id']:<14} {effect.get('default_gain_db', 0):>5} dB  {effect['file']}")
        if not args.generate:
            print("\nAjoute --generate pour créer les WAV (FFmpeg requis).")
        return 0

    written = generate_catalog(args.out, catalog_path=args.catalog,
                               force=args.force, dry_run=args.dry_run)
    print(f"✅ {len(written)} SFX dans {args.out}")
    for path in written:
        if path.exists():
            print(f"   {path.name:<18} {human_size(path)}")
    missing = [effect["id"] for effect in catalog["effects"] if effect["id"] not in SYNTH]
    if missing:
        print(f"⚠️  Pas de recette de synthèse pour : {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
