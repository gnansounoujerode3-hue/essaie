"""Moteur de rendu : assemblage d'un Short à partir d'un ShortSpec.

Pipeline :
  1. chaque plan est normalisé (1080x1920, 30 fps, mouvement Ken Burns) ;
  2. concat des plans (jump cuts) ;
  3. composition des couches (titres, autocollants, B-roll, transitions) ;
  4. sous-titres dynamiques (ASS, mot par mot) ;
  5. mixage audio (voix + musique duckée + bruitages) ;
  6. encodage final H.264 / AAC.
"""
from __future__ import annotations

import math
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from . import fonts, graphics
from .captions import build_ass, write_ass
from .ffmpeg import concat_demuxer_list, ffmpeg_bin, probe, run
from .graphics import TextLayer
from .spec import Broll, ShortSpec, Shot, Sticker, TextOverlay

# Bandes verticales pour les titres (fraction de la hauteur)
TITLE_BANDS = {
    "top": 0.16,
    "upper": 0.28,
    "center": 0.46,
    "lower": 0.62,
    "bottom": 0.78,
}

SAFE_BOTTOM = 330
SAFE_TOP = 240

# Étalonnages colorimétriques appliqués à tous les plans : c'est ce qui fait
# que des sources heteroclites donnent l'illusion d'un meme tournage.
GRADES = {
    "standard": ["eq=contrast=1.06:saturation=1.12:brightness=-0.012", "unsharp=3:3:0.35:3:3:0.0"],
    "punch": ["eq=contrast=1.14:saturation=1.24:brightness=-0.02", "unsharp=3:3:0.55:3:3:0.0"],
    "soft": ["eq=contrast=1.02:saturation=1.04:brightness=0.005", "unsharp=3:3:0.2:3:3:0.0"],
    "none": [],
}


@dataclass
class RenderResult:
    output: Path
    duration: float = 0.0
    width: int = 0
    height: int = 0
    warnings: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    workdir: Optional[Path] = None
    layers: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "output": str(self.output),
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "warnings": self.warnings,
            "layers": self.layers,
        }


class RenderError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Filtres
# --------------------------------------------------------------------------- #
def motion_expression(motion, frames: int) -> Optional[str]:
    """Construit l'expression zoompan pour un mouvement de caméra."""
    kind = (motion.kind or "static").lower()
    start = float(motion.start_scale or 1.0)
    end = float(motion.end_scale or 1.12)
    if kind == "static" or frames <= 1:
        return None
    if abs(start - end) < 1e-6:
        start = 1.0
    zoom_out = kind in {"kenburns-out", "out", "pull-out", "zoom-out"}
    if zoom_out and end >= start:
        start, end = end, start
    step = (end - start) / max(frames - 1, 1)
    hi, lo = max(end, start), min(start, end)
    if kind in {"kenburns-in", "in", "push-in", "zoom-in"} or zoom_out:
        z = f"max({lo:.4f},min({hi:.4f},{start:.4f}+{step:.7f}*on))"
        return (
            f"zoompan=z='{z}':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
        )
    if kind in {"left", "pan-left"}:
        return (
            f"zoompan=z='{hi:.4f}':d=1:"
            f"x='(iw-iw/zoom)*on/{max(frames, 1)}':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
        )
    if kind in {"right", "pan-right"}:
        return (
            f"zoompan=z='{hi:.4f}':d=1:"
            f"x='(iw-iw/zoom)*(1-on/{max(frames, 1)})':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
        )
    if kind in {"up", "pan-up"}:
        return (
            f"zoompan=z='{hi:.4f}':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{max(frames, 1)})':s=1080x1920:fps=30"
        )
    if kind in {"shake", "handheld"}:
        return (
            f"zoompan=z='min({start:.4f}+{step:.7f}*on,{hi:.4f})':d=1:"
            f"x='iw/2-(iw/zoom/2)+14*sin(on/2.3)':y='ih/2-(ih/zoom/2)+9*cos(on/3.1)':s=1080x1920:fps=30"
        )
    return None


def position_expression(position: str, safe_zone=None) -> Tuple[str, str]:
    """Expressions (x, y) d'un overlay selon son ancre et la safe zone."""
    left = int(getattr(safe_zone, "left", 80))
    right = int(getattr(safe_zone, "right", 180))
    top = int(getattr(safe_zone, "top", SAFE_TOP))
    bottom = int(getattr(safe_zone, "bottom", SAFE_BOTTOM))
    if position in TITLE_BANDS:
        frac = TITLE_BANDS[position]
        return "(W-w)/2", f"{frac}*H-h/2"
    if position == "top-left":
        return str(left), str(top)
    if position == "top-right":
        return f"W-w-{right}", str(top)
    if position == "bottom-left":
        return str(left), f"H-h-{bottom}"
    if position == "bottom-right":
        return f"W-w-{right}", f"H-h-{bottom}"
    if position == "middle-left":
        return str(left), "(H-h)/2"
    if position == "middle-right":
        return f"W-w-{right}", "(H-h)/2"
    return "(W-w)/2", "(H-h)/2"


# --------------------------------------------------------------------------- #
# Renderer
# --------------------------------------------------------------------------- #
class Renderer:
    """Compile un ShortSpec en fichier vidéo final."""

    def __init__(self, spec: ShortSpec, root: Optional[Path] = None, workdir: Optional[Path] = None, verbose: bool = False):
        self.spec = spec
        self.root = Path(root) if root else Path.cwd()
        self.verbose = verbose
        self.workdir = Path(workdir) if workdir else (self.root / "output" / ".work" / spec.slug)
        self.warnings: List[str] = []
        self.layer_names: List[str] = []
        self._input_index = 0
        self._args: List[str] = []
        self._filters: List[str] = []
        self._cur = "v0"
        self._n = 0

    # -- utilitaires ---------------------------------------------------- #
    def _abs(self, path: str | Path) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (self.root / p)

    def _add_input(self, args: Sequence[str]) -> int:
        idx = self._input_index
        self._args.extend(args)
        self._input_index += 1
        return idx

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  · {msg}")

    def _next_label(self) -> str:
        self._n += 1
        return f"v{self._n}"

    # -- 1. plans ------------------------------------------------------- #
    def _build_shot_clips(self) -> List[Path]:
        clips: List[Path] = []
        for i, shot in enumerate(self.spec.shots):
            clip = self.workdir / f"shot_{i:02d}.mp4"
            frames = max(1, int(round(shot.duration * self.spec.fps)))
            source = shot.source
            if source:
                src = self._abs(source)
                if not src.exists():
                    self.warnings.append(f"Source manquante ({shot.id or i}) — fond généré à la place.")
                    source = None
            W, H = self.spec.width, self.spec.height
            src_w = 0
            if source:
                src = self._abs(source)
                info = probe(src)
                src_w = info.width
                args = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y"]
                if info.kind == "image":
                    args += ["-loop", "1", "-framerate", str(self.spec.fps), "-t", f"{shot.duration:.3f}", "-i", str(src)]
                else:
                    if shot.source_loop:
                        args += ["-stream_loop", "-1"]
                    args += ["-ss", f"{shot.source_in:.3f}", "-t", f"{shot.duration:.3f}", "-i", str(src)]
            else:
                bg = self.workdir / f"bg_{i:02d}.png"
                img = graphics.gradient_background(
                    W, H, [shot.fallback_color, graphics.mix(shot.fallback_color, self.spec.brand.paper, 0.35)]
                ).convert("RGBA")
                img.alpha_composite(graphics.noise_texture(W, H, 16, seed=i + self.spec.seed))
                img.alpha_composite(graphics.vignette((W, H), 70))
                img.save(bg)
                args = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(self.spec.fps), "-t", f"{shot.duration:.3f}", "-i", str(bg)]

            # Pré-échelle adaptative : on n'agrandit jamais au-delà de 2x la
            # largeur cible (sinon les sources petites deviennent floues).
            if src_w:
                factor = min(2.0, max(1.0, src_w / float(W)))
            else:
                factor = 2.0
            pre_w = int(W * factor) // 2 * 2
            pre_h = int(H * factor) // 2 * 2
            chain = [
                f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase:flags=lanczos",
                f"crop={pre_w}:{pre_h}",
                "setsar=1",
            ]
            if self.spec.grade != "none":
                chain += GRADES.get(self.spec.grade, GRADES["standard"])
            zoom = motion_expression(shot.motion, frames)
            if zoom:
                chain.append(zoom)
            else:
                chain.append(f"scale={W}:{H}:flags=lanczos")
            chain += [f"fps={self.spec.fps}", "format=yuv420p"]

            args += [
                "-vf", ",".join(chain),
                "-an",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "16",
                "-pix_fmt", "yuv420p",
                "-r", str(self.spec.fps),
                "-t", f"{shot.duration:.3f}",
                str(clip),
            ]
            self._log(f"plan {shot.id or i} — {shot.duration:.2f}s — {Path(str(source)).name if source else 'fond généré'}")
            run(args)
            clips.append(clip)
        return clips

    # -- 2. concat ------------------------------------------------------ #
    def _concat(self, clips: List[Path]) -> Path:
        base = self.workdir / "base.mp4"
        lst = concat_demuxer_list(clips, self.workdir / "concat.txt")
        run(
            [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)]
        )
        return base

    # -- 3. couches ----------------------------------------------------- #
    def _overlay(self, label: str, x_expr: str, y_expr: str, at: float, duration: float) -> None:
        """Compose une couche déjà filtrée sur la chaîne vidéo courante."""
        out = self._next_label()
        self._filters.append(
            f"[{self._cur}][{label}]overlay=x={x_expr}:y={y_expr}:repeatlast=1:shortest=0:enable='between(t,{at:.3f},{at + duration:.3f})'[{out}]"
        )
        self._cur = out

    def _add_overlay_layer(
        self,
        image: TextLayer,
        *,
        at: float,
        duration: float,
        position: str = "center",
        effect: str = "none",
        scale: float = 1.0,
        opacity: float = 1.0,
        rotation: float = 0.0,
        name: str = "layer",
    ) -> None:
        """Ajoute une couche PNG sur la timeline."""
        png = self.workdir / f"layer_{self._n:03d}.png"
        image.save(png)
        # Toutes les couches partent à t=0 : l'activation se fait avec
        # `enable`, ce qui évite à framesync de mettre en attente des secondes
        # d'images avant le début d'un overlay tardif.
        # Une image statique suffit : overlay répète sa dernière frame.
        # Ne pas boucler l'image en entrée (30 fps × toute la durée pour
        # chaque couche), ce qui gonflerait le graphe à plusieurs gigaoctets.
        idx = self._add_input(["-i", str(png)])
        chain = ["format=rgba"]
        if rotation:
            chain.append(f"rotate={rotation * math.pi / 180:.5f}:ow=rotw(iw):oh=roth(ih):c=none")
        if scale != 1.0:
            chain.append(f"scale=iw*{scale:.4f}:ih*{scale:.4f}:eval=init")
        if effect in ("pop", "pop-in"):
            # Léger surdimensionnement statique; l'animation de caméra est
            # portée par le plan sous-jacent, sans décoder 30 PNG/s/couche.
            chain.append("scale=iw*1.035:ih*1.035:eval=init")
        elif effect in ("shake", "impact"):
            chain.append("scale=iw*1.015:ih*1.015:eval=init")
        # fade/slide sont volontairement instantanés sur les couches PNG
        # uniques. Flash/whip/dip sont appliqués au plan vidéo lui-même.
        if opacity < 1.0:
            chain.append(f"colorchannelmixer=aa={opacity:.3f}")

        label = f"lay{self._n}"
        self._filters.append(f"[{idx}:v]{','.join(chain)}[{label}]")
        x_expr, y_expr = position_expression(position, self.spec.safe_zone)
        self._overlay(label, x_expr, y_expr, at, duration)
        self.layer_names.append(f"{name} {position} @{at:.2f}s")

    def _add_broll(self, broll: Broll, shot: Shot, shot_start: float) -> None:
        src = self._abs(broll.source)
        if not src.exists():
            self.warnings.append(f"B-roll introuvable: {broll.source}")
            return
        at = shot_start + (broll.at or 0.0)
        duration = broll.duration or max(0.5, min(shot.duration - (broll.at or 0.0), 2.5))
        width = int(broll.width)
        height = int(broll.height) if broll.height else None
        info = probe(src)

        if info.kind == "image":
            png = self.workdir / f"broll_{self._n:03d}.png"
            img = graphics.rounded_image(src, width, height, radius=broll.radius, border=6 if broll.border else 0)
            img.save(png)
            idx = self._add_input(["-i", str(png)])
            chain = ["format=rgba"]
        else:
            # tpad clone la première image jusqu'à l'instant d'apparition, puis
            # laisse défiler le clip : la piste démarre à t=0 et framesync n'a
            # pas besoin de mettre en mémoire toute la vidéo principale.
            idx = self._add_input(["-stream_loop", "-1", "-ss", "0", "-t", f"{duration:.3f}", "-i", str(src)])
            chain = [f"tpad=start_mode=clone:start_duration={at:.3f}", f"scale={width}:-2:flags=lanczos", "format=rgba"]
        if broll.opacity < 1.0:
            chain.append(f"colorchannelmixer=aa={broll.opacity:.3f}")

        label = f"br{self._n}"
        self._filters.append(f"[{idx}:v]{','.join(chain)}[{label}]")
        x_expr, y_expr = position_expression(broll.position, self.spec.safe_zone)
        self._overlay(label, x_expr, y_expr, at, duration)
        self.layer_names.append(f"broll {Path(broll.source).name} @{at:.2f}s")

    def _add_transition(self, at: float, kind: str) -> None:
        """Flash, whip-flou ou dip directement dans la chaîne vidéo.

        On évite un overlay plein écran par coupe : les filtres à activation
        temporelle sont bien plus légers et ne créent pas de files PTS.
        """
        if kind in ("flash", "zoom"):
            dur = 0.10
            filt = f"eq=brightness=0.72:contrast=1.08:enable='between(t,{at:.3f},{at + dur:.3f})'"
        elif kind == "whip":
            dur = 0.16
            filt = f"gblur=sigma=4:steps=1:enable='between(t,{at:.3f},{at + dur:.3f})'"
        elif kind in ("dip", "fade-black"):
            dur = 0.18
            filt = f"eq=brightness=-0.55:enable='between(t,{at:.3f},{at + dur:.3f})'"
        elif kind == "glitch":
            dur = 0.12
            filt = f"rgbashift=rh=5:bh=-5:rv=1:bv=-1:enable='between(t,{at:.3f},{at + dur:.3f})'"
        else:
            return
        out = self._next_label()
        self._filters.append(f"[{self._cur}]{filt}[{out}]")
        self._cur = out
        self.layer_names.append(f"transition {kind} @{at:.2f}s")

    # -- 4. rendu complet ------------------------------------------------ #
    def render(self, output: Optional[str | Path] = None) -> RenderResult:
        spec = self.spec
        self.workdir.mkdir(parents=True, exist_ok=True)
        output_value = str(output) if output is not None else spec.output
        output_value = output_value.replace("{slug}", spec.slug)
        out_path = Path(output_value)
        if not out_path.is_absolute():
            out_path = self.root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        for issue in spec.validate(self.root):
            self.warnings.append(issue)

        clips = self._build_shot_clips()
        base = self._concat(clips)

        self._args = []
        self._input_index = 0
        self._filters = []
        self.layer_names = []
        self._cur = "v0"
        self._n = 0
        base_idx = self._add_input(["-i", str(base)])
        self._filters.append(f"[{base_idx}:v]setsar=1,fps={spec.fps},format=yuv420p[v0]")

        shot_start = 0.0
        for i, shot in enumerate(spec.shots):
            for text in shot.texts:
                self._add_text_overlay(text, shot_start)
            for sticker in shot.stickers:
                self._add_sticker(sticker, shot_start)
            for broll in shot.broll:
                self._add_broll(broll, shot, shot_start)
            shot_start += shot.duration
            if i < len(spec.shots) - 1 and shot.transition and shot.transition != "cut":
                self._add_transition(shot_start - 0.01, shot.transition)

        if spec.hook.text:
            self._add_hook_layer()
        if spec.cta and spec.cta.text:
            self._add_cta_layer()

        if spec.captions:
            ass_path = self.workdir / "captions.ass"
            ass, _boxes = build_ass(
                spec,
                default_font=spec.brand.font_caption,
                default_size=74,
                default_color=spec.brand.ink,
                highlight_color=spec.brand.primary,
                bg_color=spec.brand.paper,
            )
            write_ass(ass_path, ass)
            fonts.fontconfig_file()
            self._filters.append(
                f"[{self._cur}]subtitles=filename='{ass_path}':fontsdir='{fonts.FONT_DIR}':original_size={spec.width}x{spec.height}[{self._next_label()}]"
            )
            self._cur = self._filters[-1].split("[")[-1].rstrip("]")

        audio_chain, audio_chains = self._build_audio_graph()
        self._filters.extend(audio_chains)

        filter_complex = ";".join(self._filters)
        args = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y"]
        args += self._args
        args += ["-filter_complex_threads", "2", "-filter_complex", filter_complex]
        args += ["-map", f"[{self._cur}]"]
        if audio_chain:
            args += ["-map", audio_chain]
        args += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-threads", "2",
            "-crf", "19",
            "-profile:v", "high",
            "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-r", str(spec.fps),
            "-movflags", "+faststart",
        ]
        if audio_chain:
            args += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
        args += ["-t", f"{spec.duration:.3f}", str(out_path)]

        env = dict(os.environ)
        env["FONTCONFIG_FILE"] = str(fonts.fontconfig_file())
        proc = subprocess.run(args, capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            tail = "\n".join((proc.stderr or "").strip().splitlines()[-30:])
            raise RenderError(f"Rendu ffmpeg échoué :\n{tail}\n\nFiltre :\n{filter_complex[:2000]}")

        info = probe(out_path)
        return RenderResult(
            output=out_path,
            duration=info.duration,
            width=info.width or spec.width,
            height=info.height or spec.height,
            warnings=self.warnings,
            workdir=self.workdir,
            layers=self.layer_names,
        )

    # -- couches titre / hook / cta ------------------------------------ #
    def _add_text_overlay(self, text: TextOverlay, shot_start: float) -> None:
        spec = self.spec
        at = shot_start + text.at
        duration = max(0.3, text.duration)
        color = text.color or spec.brand.ink
        accent = text.accent or spec.brand.primary
        layer = graphics.render_text_layer(
            text.text,
            font=text.font or spec.brand.font_title,
            size=text.size,
            color=color,
            accent=accent,
            max_width=min(text.max_width, spec.width - 2 * max(spec.safe_zone.left, spec.safe_zone.right)),
            highlights=text.highlights,
            stroke=6,
            stroke_color=spec.brand.paper,
            shadow=10,
            shadow_color="#000000",
            background="#000000" if text.background else None,
            background_opacity=0.55 if text.background else 0.0,
            uppercase=True,
        )
        self._add_overlay_layer(
            layer,
            at=at,
            duration=duration,
            position=text.position if text.position in TITLE_BANDS else "center",
            effect=text.effect,
            rotation=text.rotation,
            name="titre",
        )

    def _add_sticker(self, sticker: Sticker, shot_start: float) -> None:
        spec = self.spec
        at = shot_start + (sticker.at or 0.0)
        duration = sticker.duration or 2.0
        if sticker.image:
            src = self._abs(sticker.image)
            if not src.exists():
                self.warnings.append(f"Autocollant introuvable: {sticker.image}")
                return
            layer = graphics.TextLayer(graphics.rounded_image(src, 320, 320, radius=64, border=0).copy())
        else:
            layer = graphics.render_sticker(
                sticker.text,
                font=spec.brand.font_sticker,
                size=52,
                fg=spec.brand.paper,
                bg=spec.brand.accent,
                border="#000000",
                max_width=spec.width - spec.safe_zone.left - spec.safe_zone.right,
                rotate=sticker.rotation,
            )
        self._add_overlay_layer(
            layer,
            at=at,
            duration=duration,
            position=sticker.position,
            scale=sticker.scale,
            opacity=sticker.opacity,
            rotation=sticker.rotation,
            name="sticker",
        )

    def _add_hook_layer(self) -> None:
        spec = self.spec
        hook = spec.hook
        layer = graphics.render_text_layer(
            hook.text,
            font=spec.brand.font_title,
            size=112,
            color=spec.brand.ink,
            accent=spec.brand.accent,
            max_width=spec.width - 2 * max(spec.safe_zone.left, spec.safe_zone.right),
            stroke=8,
            stroke_color=spec.brand.paper,
            shadow=16,
            uppercase=True,
        )
        self._add_overlay_layer(layer, at=0.0, duration=hook.duration, position="upper", effect="pop", name="hook")
        if hook.subtext:
            sub = graphics.render_text_layer(
                hook.subtext,
                font=spec.brand.font_caption,
                size=62,
                color=spec.brand.ink,
                max_width=spec.width - 2 * max(spec.safe_zone.left, spec.safe_zone.right),
                stroke=4,
                stroke_color=spec.brand.paper,
                shadow=8,
                uppercase=True,
            )
            self._add_overlay_layer(sub, at=0.2, duration=max(0.5, hook.duration - 0.2), position="center", effect="fade", name="hook-sub")
        if hook.badge:
            badge = graphics.render_sticker(
                hook.badge,
                font=spec.brand.font_sticker,
                size=42,
                fg=spec.brand.paper,
                bg=spec.brand.primary,
                border="#000000",
                max_width=spec.width - spec.safe_zone.left - spec.safe_zone.right,
            )
            self._add_overlay_layer(badge, at=0.05, duration=max(0.5, hook.duration - 0.2), position="top-right", effect="pop", name="badge")

    def _add_cta_layer(self) -> None:
        spec = self.spec
        cta = spec.cta
        assert cta is not None
        at = max(0.0, cta.at)
        duration = max(0.5, cta.duration)
        layer = graphics.render_text_layer(
            cta.text,
            font=spec.brand.font_title,
            size=92,
            color=spec.brand.ink,
            accent=spec.brand.primary,
            max_width=spec.width - 2 * max(spec.safe_zone.left, spec.safe_zone.right),
            stroke=7,
            stroke_color=spec.brand.paper,
            shadow=12,
            uppercase=True,
        )
        self._add_overlay_layer(layer, at=at, duration=duration, position="center", effect="pop", name="cta")
        if cta.subtext:
            sub = graphics.render_text_layer(
                cta.subtext,
                font=spec.brand.font_caption,
                size=50,
                color=spec.brand.ink,
                max_width=spec.width - 2 * max(spec.safe_zone.left, spec.safe_zone.right),
                stroke=4,
                stroke_color=spec.brand.paper,
                shadow=8,
                uppercase=True,
            )
            self._add_overlay_layer(sub, at=at + 0.25, duration=max(0.4, duration - 0.25), position="lower", effect="fade", name="cta-sub")

    # -- audio ------------------------------------------------------------ #
    def _build_audio_graph(self) -> Tuple[str, List[str]]:
        spec = self.spec
        args: List[str] = []
        chains: List[str] = []
        mix_inputs: List[str] = []

        vo_path = self._abs(spec.voiceover.path) if spec.voiceover.path else None
        mus_path = self._abs(spec.music.path) if spec.music.path else None
        sidechain_required = bool(mus_path and mus_path.exists() and spec.music.duck)

        if vo_path and vo_path.exists():
            vo_idx = self._add_input(["-i", str(vo_path)])
            chains.append(f"[{vo_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[vo_fmt]")
            if spec.voiceover.speed and abs(spec.voiceover.speed - 1.0) > 0.01:
                chains.append(f"[vo_fmt]atempo={spec.voiceover.speed:.3f}[vo_spd]")
            else:
                chains.append("[vo_fmt]anull[vo_spd]")
            vo_label = "vo_spd"
            if spec.voiceover.start > 0:
                delay = int(max(0.0, spec.voiceover.start) * 1000)
                chains.append(f"[vo_spd]adelay={delay}|{delay}[vo_delayed]")
                vo_label = "vo_delayed"
            vo_chain = (
                f"[{vo_label}]highpass=f=85,lowpass=f=13000,dynaudnorm=f=180:g=12:p=0.7,"
                f"volume={spec.voiceover.gain_db}dB"
            )
            chains.append(vo_chain + (",asplit=2[vo_main][vo_sc]" if sidechain_required else "[vo_main]"))
            mix_inputs.append("vo_main")
        else:
            if spec.voiceover.path:
                self.warnings.append(f"Voice-over introuvable: {spec.voiceover.path}")
            sil_idx = self._add_input(
                ["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={spec.duration:.3f}"]
            )
            silence_chain = f"[{sil_idx}:a]"
            chains.append(silence_chain + ("asplit=2[vo_main][vo_sc]" if sidechain_required else "anull[vo_main]"))
            mix_inputs.append("vo_main")

        if mus_path and mus_path.exists():
            mus_idx = self._add_input(["-i", str(mus_path)])
            chains.append(
                f"[{mus_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"atrim=0:{spec.duration:.3f},asetpts=N/SR/TB,"
                f"afade=t=in:st=0:d={spec.music.fade_in:.2f},"
                f"afade=t=out:st={max(0.0, spec.duration - spec.music.fade_out):.3f}:d={spec.music.fade_out:.2f},"
                f"volume={spec.music.gain_db}dB[mus_raw]"
            )
            if sidechain_required:
                chains.append("[mus_raw][vo_sc]sidechaincompress=threshold=0.02:ratio=9:attack=8:release=320[mus]")
            else:
                chains.append("[mus_raw]anull[mus]")
            mix_inputs.append("mus")
        elif spec.music.path:
            self.warnings.append(f"Musique introuvable: {spec.music.path}")

        for i, s in enumerate(spec.sfx):
            path = self._abs(s.path)
            if not path.exists():
                self.warnings.append(f"Bruitage introuvable: {s.path}")
                continue
            idx = self._add_input(["-i", str(path)])
            delay_ms = int(max(0.0, s.at) * 1000)
            dur = s.duration or 0.0
            trim = f"atrim=0:{dur:.3f}," if dur else ""
            chains.append(
                f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"{trim}adelay={delay_ms}|{delay_ms},volume={s.gain_db}dB[sfx{i}]"
            )
            mix_inputs.append(f"sfx{i}")

        if not mix_inputs:
            sil_idx = self._add_input(
                ["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={spec.duration:.3f}"]
            )
            chains.append(f"[{sil_idx}:a]anull[mixed]")
        elif len(mix_inputs) == 1:
            chains.append(f"[{mix_inputs[0]}]anull[mixed]")
        else:
            chains.append(
                "".join(f"[{m}]" for m in mix_inputs)
                + f"amix=inputs={len(mix_inputs)}:duration=longest:dropout_transition=0:normalize=0[mixed]"
            )

        chains.append(
            f"[mixed]apad,atrim=0:{spec.duration:.3f},"
            "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.97:attack=5:release=50[aout]"
        )
        return "[aout]", chains


def render_spec(spec: ShortSpec, output: Optional[str | Path] = None, root: Optional[Path] = None, verbose: bool = False) -> RenderResult:
    """Raccourci : rend un ShortSpec en MP4."""
    return Renderer(spec, root=root, verbose=verbose).render(output)
