"""Contrôle qualité & score de performance d'un Short.

Le score (/100) operationalise la méthode : hook, rythme, sous-titres,
zone de sécurité, CTA, boucle, audio, format. Chaque contrôle renvoie un
verdict, une note et une action corrective.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .captions import build_ass, coverage
from .ffmpeg import ffmpeg_bin
from .planner import rhythm_metrics, score_hook
from .spec import ShortSpec

IDEAL_MIN = 15.0
IDEAL_MAX = 45.0
TARGET_LUFS = -14.0


@dataclass
class Check:
    name: str
    score: float  # 0..1
    weight: float
    detail: str = ""
    advice: str = ""
    status: str = "ok"  # ok | warn | fail

    @property
    def points(self) -> float:
        return self.score * self.weight


@dataclass
class QAReport:
    spec_title: str = ""
    total: float = 0.0
    max_total: float = 0.0
    grade: str = "C"
    checks: List[Check] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def add(self, check: Check) -> None:
        self.checks.append(check)
        self.max_total += check.weight
        self.total += check.points

    @property
    def score(self) -> int:
        if self.max_total <= 0:
            return 0
        return int(round(100 * self.total / self.max_total))

    @property
    def failures(self) -> List[Check]:
        return [c for c in self.checks if c.status == "fail"]

    @property
    def warnings(self) -> List[Check]:
        return [c for c in self.checks if c.status == "warn"]

    def to_dict(self) -> dict:
        return {
            "title": self.spec_title,
            "score": self.score,
            "grade": self.grade,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "score": round(c.score * 100),
                    "weight": c.weight,
                    "detail": c.detail,
                    "advice": c.advice,
                }
                for c in self.checks
            ],
            "metrics": self.metrics,
        }

    def render(self) -> str:
        icons = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
        lines = [
            f"SCORE : {self.score}/100  ({self.grade})  —  {self.spec_title}",
            "-" * 72,
        ]
        for c in self.checks:
            lines.append(
                f"{icons.get(c.status, '•')} {c.name:<26} {round(c.score * 100):>3}/100  "
                f"[{c.points:4.1f}/{c.weight:4.1f}]  {c.detail}"
            )
            if c.advice and c.status != "ok":
                lines.append(f"    → {c.advice}")
        lines.append("-" * 72)
        lines.append(f"TOTAL : {self.score}/100   métriques : {self.metrics}")
        return "\n".join(lines)


def grade_for(score: int) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def measure_loudness(path: str | Path) -> dict:
    """Mesure la loudness intégrée (EBU R128) d'un média."""
    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    text = (proc.stderr or "") + (proc.stdout or "")
    out = {"integrated_lufs": None, "true_peak_db": None, "lra": None}
    m = re.findall(r"Integrated loudness:\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", text)
    if m:
        out["integrated_lufs"] = float(m[-1])
    m = re.findall(r"True peak:\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", text)
    if m:
        out["true_peak_db"] = float(m[-1])
    m = re.findall(r"Loudness range:\s*LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", text)
    if m:
        out["lra"] = float(m[-1])
    return out


def analyze(spec: ShortSpec, output: Optional[str | Path] = None, root: Optional[Path] = None) -> QAReport:
    """Analyse un Short (spec seule ou spec + fichier rendu)."""
    report = QAReport(spec_title=spec.title)
    root = Path(root) if root else Path.cwd()

    # 1. FORMAT -------------------------------------------------------
    if spec.width * 16 == spec.height * 9:
        report.add(Check("Format 9:16", 1.0, 8, f"{spec.width}x{spec.height} ✓", status="ok"))
    else:
        report.add(Check("Format 9:16", 0.0, 8, f"{spec.width}x{spec.height}", "Utiliser 1080x1920.", "fail"))

    # 2. DURÉE --------------------------------------------------------
    if IDEAL_MIN <= spec.duration <= IDEAL_MAX:
        report.add(Check("Durée", 1.0, 10, f"{spec.duration:.1f}s ✓", status="ok"))
    elif spec.duration < IDEAL_MIN:
        report.add(Check("Durée", 0.5, 10, f"{spec.duration:.1f}s", "Viser 15-45 s.", "warn"))
    else:
        report.add(Check("Durée", 0.45, 10, f"{spec.duration:.1f}s", "Couper sous 45 s (60 s max).", "warn"))

    # 3. HOOK ---------------------------------------------------------
    hook = spec.hook
    if hook.text:
        hs = score_hook(hook.text)
        words = len(hook.text.split())
        s = min(1.0, hs / 85)
        if hook.duration <= 3.2:
            s = min(1.0, s + 0.15)
        report.add(
            Check(
                "Hook",
                s,
                15,
                f"« {hook.text[:42]} » ({words} mots, {hook.duration:.1f}s) — force {hs}/100",
                "Accroche ≤ 8 mots, 3 s max, chiffre ou question.",
                "ok" if hs >= 70 else "warn",
            )
        )
    else:
        report.add(Check("Hook", 0.0, 15, "aucun hook", "Ajouter un titre d'accroche sur les 3 premières secondes.", "fail"))

    # 4. RYTHME --------------------------------------------------------
    rhythm = rhythm_metrics(spec)
    mean_shot = rhythm["mean_shot"]
    if 1.3 <= mean_shot <= 3.2:
        score = 1.0
    elif mean_shot < 1.3:
        score = 0.7
    else:
        score = max(0.3, 1.0 - (mean_shot - 3.2) * 0.25)
    if rhythm["long_gaps"]:
        score = max(0.0, score - 0.1 * len(rhythm["long_gaps"]))
    report.add(
        Check(
            "Rythme de coupe",
            score,
            14,
            f"{rhythm['cuts']} coupes, moyenne {mean_shot:.1f}s/plan"
            + (f", {len(rhythm['long_gaps'])} plan(s) > 3 s" if rhythm["long_gaps"] else ""),
            "Viser 1,5 à 3 s par plan, jamais de blanc.",
            "ok" if score >= 0.8 else "warn",
        )
    )
    report.metrics.update(rhythm)

    # 5. SOUS-TITRES ----------------------------------------------------
    cov = coverage(spec)
    if not spec.captions:
        report.add(Check("Sous-titres", 0.0, 16, "aucun", "70 % des shorts sont vus sans son : ajouter des sous-titres.", "fail"))
    else:
        size_score = 1.0 if min(c.size for c in spec.captions) >= 60 else 0.6
        score = min(1.0, cov * 0.7 + 0.3) * size_score
        report.add(
            Check(
                "Sous-titres",
                score,
                16,
                f"{len(spec.captions)} lignes, couverture {cov * 100:.0f} %, taille {min(c.size for c in spec.captions)}px",
                "Couvrir 100 % de la voix, 60-90 px, centrés.",
                "ok" if cov > 0.85 else "warn",
            )
        )
        report.metrics["caption_coverage"] = round(cov, 3)

    # 6. ZONE DE SÉCURITÉ ----------------------------------------------
    issues: List[str] = []
    try:
        _ass, boxes = build_ass(spec, default_font=spec.brand.font_caption, default_size=74)
        for b in boxes:
            if b.top < spec.safe_zone.top or b.bottom > spec.height - spec.safe_zone.bottom:
                issues.append(f"légende hors zone ({b.top:.0f}-{b.bottom:.0f}px)")
                break
            if b.right > spec.width - spec.safe_zone.right:
                issues.append("légende trop à droite (boutons UI)")
                break
    except Exception as exc:  # pragma: no cover
        issues.append(f"analyse impossible: {exc}")
    if not issues:
        report.add(Check("Zone de sécurité", 1.0, 8, "textes dans la zone utile ✓", status="ok"))
    else:
        report.add(Check("Zone de sécurité", 0.2, 8, issues[0], "Centrer verticalement, éviter bas/droite.", "warn"))

    # 7. CTA / BOUCLE ---------------------------------------------------
    if spec.cta and spec.cta.text:
        late = spec.cta.at >= spec.duration - 5.0
        report.add(
            Check(
                "CTA",
                1.0 if late else 0.6,
                10,
                f"« {spec.cta.text[:30]} » à {spec.cta.at:.1f}s",
                "Placer le CTA dans les 3 dernières secondes.",
                "ok" if late else "warn",
            )
        )
    else:
        report.add(Check("CTA", 0.0, 10, "aucun appel à l'action", "Ajouter « Abonne-toi » / « Donne ton avis ».", "fail"))

    if spec.loop:
        report.add(Check("Boucle", 1.0, 6, "boucle activée ✓", status="ok"))
    else:
        report.add(Check("Boucle", 0.4, 6, "boucle désactivée", "Relier la fin au début.", "warn"))

    # 8. AUDIO -----------------------------------------------------------
    audio_points = 0.0
    audio_detail = []
    if spec.voiceover.path:
        audio_points += 0.5
        audio_detail.append("voix ✓")
    else:
        audio_detail.append("pas de voix")
    if spec.music.path:
        audio_points += 0.3
        audio_detail.append("musique ✓")
    else:
        audio_detail.append("pas de musique")
    if spec.sfx:
        audio_points += 0.2
        audio_detail.append(f"{len(spec.sfx)} SFX")
    report.add(
        Check(
            "Bande-son",
            min(1.0, audio_points),
            9,
            ", ".join(audio_detail),
            "Voix isolée + musique duckée + SFX sur les transitions.",
            "ok" if audio_points >= 0.8 else "warn",
        )
    )

    # 9. MESURES DU RENDU ------------------------------------------------
    if output:
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = root / out_path
        if out_path.exists():
            loud = measure_loudness(out_path)
            report.metrics.update({f"audio_{k}": v for k, v in loud.items()})
            if loud.get("integrated_lufs") is not None:
                diff = abs(loud["integrated_lufs"] - TARGET_LUFS)
                score = max(0.0, 1.0 - diff / 8.0)
                report.add(
                    Check(
                        "Loudness",
                        score,
                        8,
                        f"{loud['integrated_lufs']:.1f} LUFS (cible {TARGET_LUFS})",
                        "Rester autour de -14 LUFS pour les plateformes.",
                        "ok" if diff <= 2.5 else "warn",
                    )
                )
            else:
                report.add(Check("Loudness", 0.5, 8, "mesure impossible", status="warn"))
        else:
            report.add(Check("Fichier rendu", 0.0, 8, f"introuvable: {output}", "Rendre le short.", "fail"))

    report.grade = grade_for(report.score)
    return report
