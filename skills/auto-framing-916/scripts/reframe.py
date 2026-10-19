#!/usr/bin/env python3
"""Recadrage 16:9 → 9:16 : centré, fond flou ou suivi de visage."""

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
from vesk.common import SkillError, fmt_clock, write_json  # noqa: E402
from vesk.faces import detect_faces  # noqa: E402
from vesk.ffmpeg import MEDIA_EXTENSIONS, media_info  # noqa: E402
from vesk.media import smart_reframe  # noqa: E402


def process(args, media: Path, target: Path) -> None:
    info = media_info(media)
    if not info["has_video"]:
        raise SkillError(f"{media.name} n'a pas de piste vidéo.")
    mode = args.mode
    keyframes = None
    detection = None
    if mode in {"face", "track", "auto"}:
        if args.keyframes:
            from vesk.common import read_json

            data = read_json(args.keyframes)
            keyframes = data.get("keyframes", data) if isinstance(data, dict) else data
            mode = "track"
        else:
            print(f"👤 Suivi de visage sur {media.name} (1 échantillon / {args.interval}s)…")
            try:
                detection = detect_faces(media, interval=args.interval)
            except SkillError as exc:
                print(f"⚠️  {exc}")
                detection = None
            if detection and detection.get("keyframes"):
                keyframes = detection["keyframes"]
                mode = "track"
                print(f"   {len(keyframes)} keyframe(s) · visage détecté sur "
                      f"{detection['face_ratio'] * 100:.0f} % des échantillons")
            else:
                print("   aucun visage fiable → recadrage centré")
                mode = "center"
        if args.analyze and detection and not args.dry_run:
            write_json(args.analyze, detection)
            print(f"✅ Keyframes : {args.analyze}")
    if mode == "auto":
        mode = "center"
    if mode not in {"center", "blur", "track"}:
        raise SkillError(f"Mode de recadrage inconnu : {mode}")
    print(f"✂️  {info['width']}x{info['height']} → {args.width}x{args.height} ({mode})")
    smart_reframe(media, target, track=mode, keyframes=keyframes,
                  width=args.width, height=args.height, crf=args.crf,
                  preset=args.preset, sample_interval=args.interval,
                  dry_run=args.dry_run)
    print(f"✅ {target}")


def run() -> int:
    parser = base_parser(
        "Recadre automatiquement des vidéos horizontales en vertical 9:16.",
        epilog="Exemples :\n"
               "  reframe.py --media interview.mp4 --out interview-916.mp4\n"
               "  reframe.py --media podcast.mp4 --out podcast-916.mp4 --mode blur\n"
               "  reframe.py --batch ./rushes --outdir ./vertical --mode face --analyze faces.json",
    )
    parser.add_argument("--media", "-m")
    parser.add_argument("--batch", help="Dossier de vidéos à traiter")
    parser.add_argument("--out", "-o", help="Vidéo de sortie")
    parser.add_argument("--outdir", help="Dossier de sortie en mode --batch")
    parser.add_argument("--mode", choices=["auto", "center", "blur", "face"], default="face")
    parser.add_argument("--keyframes", help="Keyframes JSON existantes")
    parser.add_argument("--analyze", help="Écrire les keyframes détectées")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Échantillonnage du suivi (s)")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.batch:
        root = Path(args.batch)
        if not root.is_dir():
            raise SkillError(f"Dossier introuvable : {root}")
        output = Path(args.outdir or "vertical")
        videos = sorted(p for p in root.rglob("*") if p.suffix.lower() in MEDIA_EXTENSIONS)
        if not videos:
            raise SkillError("Aucune vidéo dans ce dossier.")
        for video in videos:
            target = output / f"{video.stem}-916.mp4"
            print(f"\n📱 {video.name}")
            process(args, video, target)
        return 0
    if not args.media:
        parser.error("indique --media ou --batch")
    media = Path(args.media)
    target = Path(args.out or f"{media.stem}-916.mp4")
    process(args, media, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
