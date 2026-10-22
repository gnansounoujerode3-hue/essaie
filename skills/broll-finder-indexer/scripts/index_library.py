#!/usr/bin/env python3
"""Indexe une bibliothèque de B-rolls/images : durées, formats, tags, embeddings optionnels."""

from __future__ import annotations

import sys
from collections import Counter
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

from vesk.assets import filter_assets, scan, write_manifest  # noqa: E402
from vesk.cli import base_parser, main_guard  # noqa: E402
from vesk.common import fmt_clock, write_json  # noqa: E402


def run() -> int:
    parser = base_parser(
        "Indexe tes rushes/B-rolls pour la recherche lexicale ou sémantique.",
        epilog="Exemples :\n"
               "  index_library.py --library ~/Footage --library ~/Downloads/broll --out library.json\n"
               "  index_library.py --library ./assets --semantic --out library.json",
    )
    parser.add_argument("--library", "-l", action="append", required=True,
                        help="Dossier (répétable)")
    parser.add_argument("--out", "-o", default="library.json")
    parser.add_argument("--no-images", action="store_true")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--min-duration", type=float)
    parser.add_argument("--orientation", choices=["vertical", "horizontal", "square"])
    parser.add_argument("--kind", choices=["video", "image"])
    parser.add_argument("--semantic", action="store_true",
                        help="Calcule les embeddings CLIP (lent, nécessite torch/transformers)")
    parser.add_argument("--cache", default=".vesk-index.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    assets = scan(args.library, recursive=not args.no_recursive,
                  include_images=not args.no_images)
    assets = filter_assets(assets, min_duration=args.min_duration,
                           orientation=args.orientation, kind=args.kind)
    if not assets:
        print("Aucun asset trouvé.")
        return 1
    if args.semantic and not args.dry_run:
        from vesk.assets import ClipIndex

        indexer = ClipIndex()
        cache = {}
        cache_path = Path(args.cache)
        if cache_path.exists():
            from vesk.common import read_json

            cache = read_json(cache_path)
        for number, asset in enumerate(assets, start=1):
            key = f"{asset['path']}|{asset.get('size_bytes')}|{indexer.model_name}"
            if key not in cache:
                cache[key] = indexer.embed_asset(asset)
                if number % 10 == 0:
                    print(f"  embeddings {number}/{len(assets)}…")
        write_json(cache_path, cache)
        asset["embedding_cached"] = True
    write_manifest(args.out, assets, roots=args.library)
    videos = [a for a in assets if a["kind"] == "video"]
    images = [a for a in assets if a["kind"] == "image"]
    total = sum(float(a.get("duration") or 0) for a in videos)
    tags = Counter(tag for asset in assets for tag in asset.get("tags", []))
    print(f"✅ {len(assets)} asset(s) indexé(s) → {args.out}")
    print(f"   vidéos : {len(videos)} ({fmt_clock(total)}) · images : {len(images)}")
    print(f"   tags fréquents : {', '.join(tag for tag, _ in tags.most_common(12)) or '—'}")
    if args.semantic:
        print("   recherche sémantique : activée (cache .vesk-index.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
