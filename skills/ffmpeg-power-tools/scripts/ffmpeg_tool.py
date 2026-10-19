#!/usr/bin/env python3
"""Couteau suisse FFmpeg : probe, compress, convert, cut, merge, gif, hardsub, batch."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
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
from vesk.common import SkillError, fmt_clock, human_size, info  # noqa: E402
from vesk.ffmpeg import (MEDIA_EXTENSIONS, audio_loudness, burn_subtitles,  # noqa: E402
                         extract_audio, extract_frame, ffmpeg, ffmpeg_bin,
                         has_filter, media_info, mux_audio, validate_media)
from vesk.media import merge_ranges, render_cut  # noqa: E402


def cmd_probe(args) -> int:
    info_ = media_info(args.input)
    if args.json:
        print(json.dumps(info_, ensure_ascii=False, indent=2))
    else:
        for key, value in info_.items():
            print(f"{key:<14} {value}")
    return 0


def cmd_compress(args) -> int:
    info_ = media_info(args.input)
    if not info_["has_video"]:
        raise SkillError("Compression vidéo : le fichier n'a pas de piste vidéo.")
    duration = info_["duration"] or 1.0
    args_out = [str(args.output)]
    video_filters = []
    if args.scale:
        video_filters.append(f"scale={args.scale}")
    if args.fps:
        video_filters.append(f"fps={args.fps}")
    vf = ["-vf", ",".join(video_filters)] if video_filters else []
    if args.target_size:
        audio_kbps = 128
        total_kbits = args.target_size * 8 * 1024
        video_kbps = max(120, int(total_kbits / duration - audio_kbps))
        video_kbps = min(video_kbps, args.max_bitrate or 50_000)
        print(f"🎯 Cible {args.target_size} Mo → vidéo ~{video_kbps} kb/s + audio {audio_kbps} kb/s")
        log = Path(tempfile.mkdtemp(prefix="vesk-pass-")) / "x264"
        common = ["-c:v", "libx264", "-b:v", f"{video_kbps}k", "-preset", args.preset,
                  "-pix_fmt", "yuv420p", *vf, "-passlogfile", str(log)]
        ffmpeg(["-i", args.input, *common, "-pass", "1", "-an", "-f", "mp4", "/dev/null"],
               dry_run=args.dry_run)
        ffmpeg(["-i", args.input, *common, "-pass", "2", "-c:a", "aac",
                "-b:a", f"{audio_kbps}k", "-movflags", "+faststart", *args_out],
               dry_run=args.dry_run)
        shutil.rmtree(log.parent, ignore_errors=True)
    else:
        ffmpeg(["-i", args.input, "-c:v", "libx264", "-crf", str(args.crf),
                "-preset", args.preset, "-pix_fmt", "yuv420p", *vf,
                "-c:a", "aac", "-b:a", args.audio_bitrate,
                "-movflags", "+faststart", *args_out], dry_run=args.dry_run)
    if not args.dry_run and args.output.exists():
        before, after = info_["size_bytes"], args.output.stat().st_size
        print(f"✅ {args.output} · {human_size(args.output)} "
              f"({(1 - after / max(1, before)) * 100:.0f} % de gain)")
    return 0


def cmd_convert(args) -> int:
    info_ = media_info(args.input)
    if args.codec:
        args_out = ["-c:v", args.codec, "-c:a", args.audio_codec or "aac"]
    elif Path(args.output).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}:
        args_out = ["-c", "copy"]
    else:
        args_out = []
    if args.no_audio or not info_["has_audio"]:
        args_out += ["-an"]
    ffmpeg(["-i", args.input, *args_out, "-movflags", "+faststart", str(args.output)],
           dry_run=args.dry_run)
    print(f"✅ {args.output}")
    return 0


def cmd_cut(args) -> int:
    start = args.start
    end = args.end if args.end is not None else start + (args.duration or 0)
    if end <= start:
        raise SkillError("--end (ou --duration) invalide.")
    ranges = [{"start": start, "end": end, "speed": 1.0}]
    if args.reencode:
        render_cut(args.input, args.output, ranges, crf=args.crf, preset=args.preset,
                   dry_run=args.dry_run)
    else:
        ffmpeg(["-ss", f"{start:.3f}", "-i", args.input, "-t", f"{end - start:.3f}",
                "-c", "copy", "-avoid_negative_ts", "make_zero", str(args.output)],
               dry_run=args.dry_run)
        print("⚡ Copie sans réencodage : la coupe tombe sur la keyframe précédente "
              "(utilise --reencode pour une coupe exacte).")
    print(f"✅ {args.output}")
    return 0


def cmd_merge(args) -> int:
    inputs = [Path(item) for item in args.inputs]
    for item in inputs:
        validate_media(item)
    from vesk.ffmpeg import concat_files

    if args.reencode:
        print("ℹ️  Concat réencodée : les clips sont d'abord normalisés par FFmpeg "
              "si les codecs diffèrent (sinon copie directe).")
    concat_files(inputs, args.output, dry_run=args.dry_run)
    print(f"✅ {args.output} ({len(inputs)} fichier(s))")
    return 0


def cmd_audio(args) -> int:
    if args.extract:
        if args.output.suffix.lower() != ".wav":
            raise SkillError("--extract écrit du WAV : utilise une sortie .wav.")
        extract_audio(args.input, args.output, sample_rate=args.sample_rate,
                      channels=args.channels, dry_run=args.dry_run)
    elif args.replace:
        mux_audio(args.input, args.audio, args.output, replace=True,
                  audio_gain_db=args.gain, dry_run=args.dry_run)
    else:
        mux_audio(args.input, args.audio, args.output, replace=False,
                  audio_gain_db=args.gain, dry_run=args.dry_run)
    print(f"✅ {args.output}")
    return 0


def cmd_gif(args) -> int:
    fps = args.fps
    width = args.width
    palette = (
        f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];"
        "[s0]palettegen=max_colors=256[p];[s1][p]paletteuse=dither=bayer"
    )
    ffmpeg(["-ss", str(args.start), "-t", str(args.duration), "-i", args.input,
            "-vf", palette, "-loop", "0", str(args.output)], dry_run=args.dry_run)
    print(f"✅ {args.output}")
    return 0


def cmd_thumbnail(args) -> int:
    for index, time in enumerate(args.times):
        target = args.output
        if len(args.times) > 1:
            target = args.output.with_name(f"{args.output.stem}-{index + 1:02d}{args.output.suffix}")
        extract_frame(args.input, target, time=time, width=args.width)
        print(f"✅ {target}")
    return 0


def cmd_contact(args) -> int:
    columns = args.columns
    rows = args.rows
    count = columns * rows
    vf = (f"fps=1/{args.interval},scale={args.width}:-1,tile={columns}x{rows}")
    ffmpeg(["-i", args.input, "-vf", vf, "-frames:v", "1", str(args.output)],
           dry_run=args.dry_run)
    print(f"✅ {args.output} ({count} vignettes)")
    return 0


def cmd_hardsub(args) -> int:
    subtitle = Path(args.subtitles)
    if subtitle.suffix.lower() == ".ass":
        burn_subtitles(args.input, subtitle, args.output, crf=args.crf,
                       preset=args.preset, dry_run=args.dry_run)
    else:
        if not has_filter("subtitles"):
            raise SkillError("FFmpeg sans libass (filtre subtitles).")
        escaped = subtitle.resolve().as_posix().replace(":", "\\:").replace("'", "\\'")
        ffmpeg(["-i", args.input, "-vf", f"subtitles='{escaped}'",
                "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
                "-c:a", "aac", "-b:a", "192k", str(args.output)], dry_run=args.dry_run)
    print(f"✅ {args.output}")
    return 0


def cmd_loudness(args) -> int:
    data = audio_loudness(args.input, dry_run=args.dry_run)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def _output_for(args, source: Path, suffix: str) -> Path:
    return args.outdir / f"{source.stem}{suffix}"


def cmd_batch(args) -> int:
    root = Path(args.input)
    if not root.is_dir():
        raise SkillError("--batch attend un dossier.")
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() in MEDIA_EXTENSIONS)
    if not files:
        raise SkillError("Aucun média dans ce dossier.")
    args.outdir.mkdir(parents=True, exist_ok=True)
    for media in files:
        target = _output_for(args, media, args.suffix)
        print(f"\n🎞️  {media.name}")
        args.input, args.output = media, target
        if args.action == "compress":
            cmd_compress(args)
        else:
            cmd_convert(args)
    return 0


def _common_output(parser, default: str = "out.mp4"):
    parser.add_argument("--output", "-o", type=Path, default=Path(default))
    parser.add_argument("--dry-run", action="store_true")


def run() -> int:
    parser = base_parser(
        "Boîte à outils FFmpeg : encodage, découpe, conversion, GIF, sous-titres, batch.",
        epilog="Exemples :\n"
               "  ffmpeg_tool.py probe clip.mp4 --json\n"
               "  ffmpeg_tool.py compress clip.mov -o clip.mp4 --target-size 25\n"
               "  ffmpeg_tool.py cut clip.mp4 -o extract.mp4 --start 12 --duration 8 --reencode\n"
               "  ffmpeg_tool.py hardsub clip.mp4 --subtitles subs.ass -o captioned.mp4",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="Métadonnées média")
    probe.add_argument("input", type=Path)
    probe.add_argument("--json", action="store_true")
    probe.set_defaults(func=cmd_probe)

    compress = sub.add_parser("compress", help="Compression CRF ou taille cible")
    compress.add_argument("input", type=Path)
    _common_output(compress)
    compress.add_argument("--crf", type=int, default=23)
    compress.add_argument("--target-size", type=float, help="Taille cible en Mo")
    compress.add_argument("--max-bitrate", type=int, help="Plafond vidéo en kb/s")
    compress.add_argument("--scale", help="ex : 1080:-2")
    compress.add_argument("--fps", type=float)
    compress.add_argument("--preset", default="medium")
    compress.add_argument("--audio-bitrate", default="128k")
    compress.set_defaults(func=cmd_compress)

    convert = sub.add_parser("convert", help="Conversion/remux")
    convert.add_argument("input", type=Path)
    _common_output(convert)
    convert.add_argument("--codec", help="Codec vidéo (libx264, libvpx-vp9…)")
    convert.add_argument("--audio-codec")
    convert.add_argument("--no-audio", action="store_true")
    convert.set_defaults(func=cmd_convert)

    cut = sub.add_parser("cut", help="Découper un extrait")
    cut.add_argument("input", type=Path)
    _common_output(cut, "cut.mp4")
    cut.add_argument("--start", type=float, required=True)
    cut.add_argument("--end", type=float)
    cut.add_argument("--duration", type=float)
    cut.add_argument("--reencode", action="store_true")
    cut.add_argument("--crf", type=int, default=18)
    cut.add_argument("--preset", default="medium")
    cut.set_defaults(func=cmd_cut)

    merge = sub.add_parser("merge", help="Concaténer des fichiers")
    merge.add_argument("inputs", nargs="+", type=Path)
    _common_output(merge, "merged.mp4")
    merge.add_argument("--reencode", action="store_true")
    merge.set_defaults(func=cmd_merge)

    audio = sub.add_parser("audio", help="Extraire / remplacer / mixer l'audio")
    audio.add_argument("input", type=Path)
    audio.add_argument("--audio", type=Path, help="Piste à ajouter/remplacer")
    audio.add_argument("--extract", action="store_true")
    audio.add_argument("--replace", action="store_true")
    _common_output(audio, "audio.wav")
    audio.add_argument("--sample-rate", type=int, default=48000)
    audio.add_argument("--channels", type=int, default=2)
    audio.add_argument("--gain", type=float, default=0.0, help="Gain en dB")
    audio.set_defaults(func=cmd_audio)

    gif = sub.add_parser("gif", help="GIF optimisé (palette)")
    gif.add_argument("input", type=Path)
    _common_output(gif, "anim.gif")
    gif.add_argument("--start", type=float, default=0.0)
    gif.add_argument("--duration", type=float, default=3.0)
    gif.add_argument("--fps", type=int, default=15)
    gif.add_argument("--width", type=int, default=480)
    gif.set_defaults(func=cmd_gif)

    thumb = sub.add_parser("thumbnail", help="Extraire une/des vignette(s)")
    thumb.add_argument("input", type=Path)
    _common_output(thumb, "thumb.jpg")
    thumb.add_argument("--times", type=float, nargs="+", default=[0.5])
    thumb.add_argument("--width", type=int, default=640)
    thumb.set_defaults(func=cmd_thumbnail)

    contact = sub.add_parser("contact", help="Planche de vignettes")
    contact.add_argument("input", type=Path)
    _common_output(contact, "contact.jpg")
    contact.add_argument("--interval", type=float, default=2.0)
    contact.add_argument("--columns", type=int, default=5)
    contact.add_argument("--rows", type=int, default=4)
    contact.add_argument("--width", type=int, default=320)
    contact.set_defaults(func=cmd_contact)

    hardsub = sub.add_parser("hardsub", help="Incruster des sous-titres SRT/ASS")
    hardsub.add_argument("input", type=Path)
    hardsub.add_argument("--subtitles", type=Path, required=True)
    _common_output(hardsub, "subtitled.mp4")
    hardsub.add_argument("--crf", type=int, default=18)
    hardsub.add_argument("--preset", default="medium")
    hardsub.set_defaults(func=cmd_hardsub)

    loudness = sub.add_parser("loudness", help="Mesure LUFS/true peak")
    loudness.add_argument("input", type=Path)
    loudness.add_argument("--dry-run", action="store_true")
    loudness.set_defaults(func=cmd_loudness)

    batch = sub.add_parser("batch", help="Appliquer compress/convert à un dossier")
    batch.add_argument("input", type=Path)
    batch.add_argument("--outdir", type=Path, default=Path("output"))
    batch.add_argument("--action", choices=["compress", "convert"], default="compress")
    batch.add_argument("--suffix", default="-compressed.mp4")
    batch.add_argument("--crf", type=int, default=23)
    batch.add_argument("--target-size", type=float)
    batch.add_argument("--max-bitrate", type=int)
    batch.add_argument("--scale")
    batch.add_argument("--fps", type=float)
    batch.add_argument("--preset", default="medium")
    batch.add_argument("--audio-bitrate", default="128k")
    batch.add_argument("--codec")
    batch.add_argument("--audio-codec")
    batch.add_argument("--no-audio", action="store_true")
    batch.add_argument("--dry-run", action="store_true")
    batch.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    if hasattr(args, "output"):
        args.output = Path(args.output)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
