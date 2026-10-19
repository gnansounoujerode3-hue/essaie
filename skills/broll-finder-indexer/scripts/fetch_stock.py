#!/usr/bin/env python3
"""Télécharge des B-rolls libres de droits (Pexels / Pixabay) pour une requête."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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
from vesk.common import SkillError, fmt_clock, slugify, write_json  # noqa: E402

USER_AGENT = "VESK/1.0 (video editing skills kit)"


def _get_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SkillError(f"API stock ({exc.code}) : {detail}") from exc
    except urllib.error.URLError as exc:
        raise SkillError(f"API stock injoignable : {exc.reason}") from exc


def _download(url: str, target: Path, headers: dict[str, str]) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(request, timeout=180) as response, open(temporary, "wb") as handle:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
    temporary.replace(target)


def _pexels(query: str, count: int, orientation: str, max_width: int,
            output: Path, api_key: str, dry_run: bool) -> list[dict]:
    params = urllib.parse.urlencode({
        "query": query,
        "orientation": orientation,
        "size": "medium",
        "per_page": max(3, min(80, count * 3)),
    })
    data = _get_json(f"https://api.pexels.com/videos/search?{params}",
                     {"Authorization": api_key})
    selected = []
    for video in data.get("videos", []):
        files = sorted(video.get("video_files", []),
                       key=lambda f: (f.get("width") or 0), reverse=True)
        candidates = [f for f in files
                      if (f.get("file_type") == "video/mp4")
                      and (f.get("width") or 0) <= max_width]
        best = candidates[0] if candidates else (files[-1] if files else None)
        if not best or not best.get("link"):
            continue
        target = output / f"pexels-{video['id']}-{slugify(query, max_length=30)}.mp4"
        selected.append({
            "provider": "pexels",
            "id": video["id"],
            "target": target,
            "url": best["link"],
            "width": best.get("width"),
            "height": best.get("height"),
            "duration": video.get("duration"),
            "page": video.get("url"),
            "author": (video.get("user") or {}).get("name"),
            "license": "Pexels License (usage gratuit, attribution appréciée)",
            "headers": {"Authorization": api_key},
        })
        if len(selected) >= count:
            break
    return selected


def _pixabay(query: str, count: int, orientation: str, max_width: int,
             output: Path, api_key: str, dry_run: bool) -> list[dict]:
    params = urllib.parse.urlencode({
        "key": api_key,
        "q": query,
        "video_type": "film",
        "orientation": "vertical" if orientation == "portrait" else orientation,
        "per_page": max(3, min(200, count * 3)),
        "safesearch": "true",
    })
    data = _get_json(f"https://pixabay.com/api/videos/?{params}", {})
    selected = []
    for video in data.get("hits", []):
        variants = video.get("videos", {})
        ordered = [variants.get(key) for key in ("large", "medium", "small", "tiny")]
        best = next((v for v in ordered if v and (v.get("width") or 0) <= max_width), None)
        if not best and ordered:
            best = ordered[-1]
        if not best or not best.get("url"):
            continue
        target = output / f"pixabay-{video['id']}-{slugify(query, max_length=30)}.mp4"
        selected.append({
            "provider": "pixabay",
            "id": video["id"],
            "target": target,
            "url": best["url"],
            "width": best.get("width"),
            "height": best.get("height"),
            "duration": video.get("duration"),
            "page": video.get("pageURL"),
            "author": video.get("user"),
            "license": "Pixabay Content License",
            "headers": {},
        })
        if len(selected) >= count:
            break
    return selected


def run() -> int:
    parser = base_parser(
        "Télécharge des vidéos libres de droits depuis Pexels ou Pixabay.",
        epilog="Clés API (gratuites) :\n"
               "  export PEXELS_API_KEY=...   https://www.pexels.com/api/\n"
               "  export PIXABAY_API_KEY=...  https://pixabay.com/api/docs/\n\n"
               "Exemples :\n"
               "  fetch_stock.py --query \"cafe matin\" --count 8 --out ./broll\n"
               "  fetch_stock.py --query \"city night\" --provider pixabay --orientation portrait",
    )
    parser.add_argument("--query", "-q", required=True)
    parser.add_argument("--provider", choices=["pexels", "pixabay"], default="pexels")
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--orientation", choices=["portrait", "landscape", "square"],
                        default="portrait")
    parser.add_argument("--max-width", type=int, default=1920)
    parser.add_argument("--out", "-o", default="broll")
    parser.add_argument("--api-key", help="Sinon PEXELS_API_KEY / PIXABAY_API_KEY")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_name = "PEXELS_API_KEY" if args.provider == "pexels" else "PIXABAY_API_KEY"
    api_key = args.api_key or os.environ.get(env_name)
    if not api_key:
        raise SkillError(
            f"Clé {env_name} manquante. Crée un compte gratuit et exporte la variable "
            f"(ne colle jamais de clé dans le chat).\n"
            f"Pexels : https://www.pexels.com/api/ · Pixabay : https://pixabay.com/api/docs/"
        )
    output = Path(args.out)
    if args.provider == "pexels":
        items = _pexels(args.query, args.count, args.orientation, args.max_width,
                        output, api_key, args.dry_run)
    else:
        items = _pixabay(args.query, args.count, args.orientation, args.max_width,
                         output, api_key, args.dry_run)
    if not items:
        raise SkillError("Aucun résultat pour cette requête.")
    manifest_path = output / "licenses.json"
    manifest = {"version": 1, "assets": []}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    for item in items:
        target = item["target"]
        print(f"⬇️  {item['provider']}#{item['id']} {item['width']}x{item['height']} "
              f"({fmt_clock(float(item['duration'] or 0))}) → {target.name}")
        if not args.dry_run:
            _download(item["url"], target, item["headers"])
            time.sleep(0.25)
        manifest["assets"].append({
            key: (str(value) if key == "target" else value)
            for key, value in item.items() if key != "headers"
        })
    if not args.dry_run:
        write_json(manifest_path, manifest)
        print(f"✅ {len(items)} clip(s) · licences : {manifest_path}")
    else:
        for item in items:
            print("   ", item["page"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
