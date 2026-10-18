"""Interface en ligne de commande ShortsForge.

    sf doctor                      # état de l'environnement
    sf skills list|show|prompt     # bibliothèque de skills
    sf brief --skills a,b          # brief de production
    sf plan --script "..."         # script -> ShortSpec
    sf render spec.yaml            # rendu du Short
    sf qa spec.yaml [--render]     # score de performance
    sf music|sfx                   # génération d'assets audio
    sf align spec.yaml --voice v   # synchronisation voix/sous-titres
    sf studio                      # studio web (aperçu live)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from . import __version__, skills as skills_mod
from .aligner import align_captions
from .audio_synth import render_music, render_sfx, render_sfx_library
from .captions import plan_words
from .ffmpeg import ffmpeg_bin, probe
from .planner import build_plan
from .qa import analyze
from .renderer import Renderer, render_spec
from .spec import CaptionLine, Cta, ShortSpec

# Les specs et leurs médias sont résolus depuis le dossier de travail : cela
# permet d'utiliser ShortsForge comme paquet installé dans un projet séparé.
ROOT = Path.cwd().resolve()
BUNDLED_ASSETS = Path(__file__).resolve().parent / "bundled_assets"


# --------------------------------------------------------------------------- #
def _p(*args) -> None:
    print(*args)


def _skill_ids(values: List[str]) -> List[str]:
    """Accepte des IDs séparés par espace ou par virgule."""
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


def cmd_doctor(args) -> int:
    _p(f"ShortsForge v{__version__}")
    _p("-" * 60)
    ff = ffmpeg_bin()
    _p(f"ffmpeg      : {ff}")
    try:
        from .ffmpeg import ffmpeg_bin as fb

        out = __import__("subprocess").run([ff, "-hide_banner", "-version"], capture_output=True, text=True)
        _p(f"             {out.stdout.splitlines()[0] if out.stdout else '?'}")
    except Exception as exc:
        _p(f"             ERREUR {exc}")
    for mod in ("PIL", "numpy", "yaml", "imageio_ffmpeg"):
        try:
            __import__(mod)
            _p(f"{mod:<11}: OK")
        except Exception as exc:
            _p(f"{mod:<11}: MANQUANT ({exc})")
    from . import fonts

    _p(f"polices     : {len(fonts.all_fonts())} dans {fonts.FONT_DIR}")
    asset_root = ROOT / "assets"
    if not (asset_root / "music").exists():
        asset_root = BUNDLED_ASSETS
    music = list((asset_root / "music").glob("*.mp3")) if (asset_root / "music").exists() else []
    sfx = list((asset_root / "sfx").glob("*.mp3")) if (asset_root / "sfx").exists() else []
    _p(f"musiques    : {len(music)}")
    _p(f"bruitages   : {len(sfx)}")
    _p(f"skills      : {len(skills_mod.load_all())}")
    _p("-" * 60)
    _p("OK — prêt à produire.")
    return 0


def cmd_skills(args) -> int:
    if args.action == "list":
        _p(skills_mod.index_markdown())
        return 0
    if args.action == "show":
        skill = skills_mod.get(args.id)
        _p(f"--- {skill.name} ({skill.id}) v{skill.version} ---")
        _p(skill.description)
        _p("")
        _p(skill.body)
        return 0
    if args.action == "prompt":
        _p(skills_mod.as_prompt(_skill_ids(args.skills)))
        return 0
    if args.action == "index":
        path = skills_mod.write_manifest()
        _p(f"manifest écrit : {path}")
        return 0
    return 1


def cmd_brief(args) -> int:
    text = skills_mod.compose(_skill_ids(args.skills), context=args.context or "")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        _p(f"brief écrit : {args.out}")
    else:
        _p(text)
    return 0


def cmd_plan(args) -> int:
    script = args.script
    if args.script_file:
        script = Path(args.script_file).read_text(encoding="utf-8")
    shots, captions, hook, meta = build_plan(
        script,
        duration=args.duration,
        hook_duration=args.hook_duration,
        cta=args.cta,
        sources=args.source or None,
    )
    spec = ShortSpec(
        title=args.title,
        slug=args.slug,
        duration=args.duration,
        hook=hook,
        shots=shots,
        captions=captions,
        music={
            "path": str((ROOT / "assets" / "music" / "beat_upbeat_minor.mp3")
                        if (ROOT / "assets" / "music" / "beat_upbeat_minor.mp3").exists()
                        else (BUNDLED_ASSETS / "music" / "beat_upbeat_minor.mp3")),
            "gain_db": -20,
        },
        cta=Cta(text=args.cta, subtext="1 astuce par jour", at=max(0.0, args.duration - 3.2), duration=3.2),
        output=f"output/{args.slug}.mp4",
    )
    if args.out:
        spec.save(args.out)
        _p(f"spec écrit : {args.out}")
        _p(f"hook : {hook.text}  (score {meta['hook_score']}/100)")
        _p(f"plans : {len(shots)} — {sum(s.duration for s in shots):.1f}s")
    else:
        _p(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_render(args) -> int:
    spec = ShortSpec.load(args.spec)
    if args.output:
        spec.output = args.output
    t0 = time.time()
    _p(f"Rendu de « {spec.title} » …")
    result = render_spec(spec, root=ROOT, verbose=args.verbose)
    dt = time.time() - t0
    _p(f"✔ {result.output}  ({result.duration:.1f}s, {result.width}x{result.height}, {dt:.0f}s de calcul)")
    for w in result.warnings:
        _p(f"  ⚠ {w}")
    if args.qa:
        report = analyze(spec, result.output, root=ROOT)
        _p("")
        _p(report.render())
    return 0


def cmd_qa(args) -> int:
    spec = ShortSpec.load(args.spec)
    output = args.output or spec.output.replace("{slug}", spec.slug)
    if args.render:
        result = render_spec(spec, root=ROOT, verbose=args.verbose)
        output = result.output
    report = analyze(spec, output, root=ROOT)
    if args.json:
        _p(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        _p(report.render())
    blocking = [c for c in report.checks if c.status == "fail"]
    return 1 if blocking else 0


def cmd_align(args) -> int:
    spec = ShortSpec.load(args.spec)
    voice = args.voice or spec.voiceover.path
    if not voice:
        _p("Aucun voice-over fourni (--voice).")
        return 1
    spec, warnings = align_captions(spec, Path(voice))
    out = args.out or args.spec
    spec.save(out)
    _p(f"alignement écrit : {out}")
    for w in warnings:
        _p(f"  ⚠ {w}")
    return 0


def cmd_music(args) -> int:
    path = Path(args.out) if args.out else ROOT / "assets" / "music" / f"beat_{args.style}.mp3"
    render_music(path, duration=args.duration, bpm=args.bpm, style=args.style)
    _p(f"musique : {path}")
    return 0


def cmd_sfx(args) -> int:
    out = ROOT / "assets" / "sfx"
    if args.kind == "all":
        files = render_sfx_library(out)
        for k, v in files.items():
            _p(f"  {k:<8} -> {v}")
    else:
        p = render_sfx(out / f"{args.kind}.mp3", args.kind)
        _p(f"  {args.kind:<8} -> {p}")
    return 0


def cmd_batch(args) -> int:
    specs = sorted(Path(args.dir).glob("*.yaml")) + sorted(Path(args.dir).glob("*.yml")) + sorted(Path(args.dir).glob("*.json"))
    if not specs:
        _p(f"Aucun spec dans {args.dir}")
        return 1
    results = []
    for spec_path in specs:
        _p(f"\n▶ {spec_path.name}")
        try:
            spec = ShortSpec.load(spec_path)
            res = render_spec(spec, root=ROOT, verbose=args.verbose)
            rep = analyze(spec, res.output, root=ROOT)
            _p(f"  ✔ {res.output.name} — score {rep.score}/100 ({rep.grade})")
            results.append((spec_path.name, rep.score, rep.grade))
        except Exception as exc:
            _p(f"  ✖ {exc}")
            results.append((spec_path.name, 0, "E"))
    _p("\nRécapitulatif")
    for name, score, grade in results:
        _p(f"  {name:<28} {score:>3}/100  {grade}")
    return 0


def cmd_studio(args) -> int:
    from .server import serve

    serve(host=args.host, port=args.port, root=ROOT)
    return 0


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sf", description="ShortsForge — production de Shorts marketing verticaux")
    parser.add_argument("--version", action="version", version=f"ShortsForge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="état de l'environnement")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("skills", help="bibliothèque de skills")
    p.add_argument("action", choices=["list", "show", "prompt", "index"], nargs="?", default="list")
    p.add_argument("id", nargs="?", default="")
    p.add_argument("--skills", nargs="*", default=[])
    p.set_defaults(func=cmd_skills)

    p = sub.add_parser("brief", help="composer un brief de production")
    p.add_argument("--skills", nargs="+", required=True)
    p.add_argument("--context", default="")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_brief)

    p = sub.add_parser("plan", help="script -> plan de montage")
    p.add_argument("--script", default="")
    p.add_argument("--script-file", default="")
    p.add_argument("--duration", type=float, default=28.0)
    p.add_argument("--hook-duration", type=float, default=2.8)
    p.add_argument("--cta", default="Abonne-toi")
    p.add_argument("--title", default="Nouveau Short")
    p.add_argument("--slug", default="nouveau_short")
    p.add_argument("--source", nargs="*", default=[])
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("render", help="rendre un Short")
    p.add_argument("spec")
    p.add_argument("--output", default="")
    p.add_argument("--qa", action="store_true", help="afficher le score QA après rendu")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("qa", help="score de performance")
    p.add_argument("spec")
    p.add_argument("--output", default="")
    p.add_argument("--render", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_qa)

    p = sub.add_parser("align", help="aligner les sous-titres sur la voix")
    p.add_argument("spec")
    p.add_argument("--voice", default="")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_align)

    p = sub.add_parser("music", help="générer une nappe musicale")
    p.add_argument("--style", default="upbeat_minor")
    p.add_argument("--duration", type=float, default=30.0)
    p.add_argument("--bpm", type=int, default=128)
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_music)

    p = sub.add_parser("sfx", help="générer des bruitages")
    p.add_argument("kind", nargs="?", default="all")
    p.set_defaults(func=cmd_sfx)

    p = sub.add_parser("batch", help="rendre tous les specs d'un dossier")
    p.add_argument("dir")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("studio", help="studio web (aperçu live)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    p.set_defaults(func=cmd_studio)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        _p("\nInterrompu.")
        return 130
    except BrokenPipeError:
        # Permet les usages UNIX classiques du type `sf skills prompt | head`.
        try:
            sys.stdout = open(os.devnull, "w")
        except Exception:
            pass
        return 0
    except Exception as exc:
        _p(f"✖ {type(exc).__name__}: {exc}")
        if os.environ.get("SHORTSFORGE_DEBUG"):
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())
