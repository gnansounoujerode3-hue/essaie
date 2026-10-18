"""Bibliothèque de skills : chargement, index, composition de briefs.

Chaque skill est un dossier ``skills/<id>/SKILL.md`` avec un en-tête YAML
(frontmatter) et un corps en Markdown. Le chargeur :

  * lit le frontmatter (nom, version, description, tags, entrées/sorties) ;
  * expose un index lisible par un agent ;
  * compose un « brief de production » à partir d'une sélection de skills.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
PROJECT_SKILLS_DIR = ROOT / "skills"
PACKAGE_SKILLS_DIR = PACKAGE_DIR / "skill_library"
SKILLS_DIR = PROJECT_SKILLS_DIR if PROJECT_SKILLS_DIR.exists() else PACKAGE_SKILLS_DIR

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass
class Skill:
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    when_to_use: str = ""
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    checklist: List[str] = field(default_factory=list)
    body: str = ""
    path: Optional[Path] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "when_to_use": self.when_to_use,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "checklist": self.checklist,
            "path": f"{self.id}/SKILL.md" if self.path else None,
        }

    def as_prompt(self) -> str:
        """Le skill injectable tel quel dans le contexte d'un agent."""
        return f"### SKILL :: {self.name} ({self.id})\n\n{self.body.strip()}"


def _parse_frontmatter(text: str) -> tuple[Dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    data: Dict = {}
    if yaml is not None:
        try:
            data = yaml.safe_load(raw) or {}
        except Exception:
            data = {}
    if not data:
        for line in raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
    return data, body


def load_all(root: Optional[Path] = None) -> List[Skill]:
    """Charge tous les skills du dossier ``skills/``."""
    base = Path(root) if root else SKILLS_DIR
    skills: List[Skill] = []
    if not base.exists():
        return skills
    for path in sorted(base.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        data, body = _parse_frontmatter(text)
        skill = Skill(
            id=str(data.get("id") or path.parent.name),
            name=str(data.get("name") or path.parent.name),
            description=str(data.get("description") or "").strip(),
            version=str(data.get("version") or "1.0.0"),
            tags=[str(t) for t in (data.get("tags") or [])],
            when_to_use=str(data.get("when_to_use") or "").strip(),
            inputs=[str(t) for t in (data.get("inputs") or [])],
            outputs=[str(t) for t in (data.get("outputs") or [])],
            checklist=[str(t) for t in (data.get("checklist") or [])],
            body=body.strip(),
            path=path,
        )
        skills.append(skill)
    return skills


def index() -> List[Skill]:
    return load_all()


def get(skill_id: str, root: Optional[Path] = None) -> Skill:
    for skill in load_all(root):
        if skill.id == skill_id or skill.id.replace("_", "-") == skill_id:
            return skill
    raise KeyError(f"Skill inconnu : {skill_id}")


def write_manifest(root: Optional[Path] = None) -> Path:
    """Écrit l'index machine et synchronise sa copie intégrée au paquet."""
    if root is not None:
        base = Path(root)
        source = base
    elif PROJECT_SKILLS_DIR.exists():
        base = PROJECT_SKILLS_DIR
        source = PROJECT_SKILLS_DIR
    else:
        # Laisser l'installation du paquet en lecture seule; les manifests
        # générés par l'utilisateur vont dans son dossier de travail.
        base = Path.cwd() / "skills"
        source = SKILLS_DIR
    skills = load_all(source)
    manifest = {
        "version": "1.0.0",
        "count": len(skills),
        "skills": [s.to_dict() for s in skills],
    }
    out = base / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # En mode dépôt, embarque aussi les playbooks dans le wheel. Le runtime
    # installé les lira depuis shortsforge/skill_library si le dossier source
    # skills/ n'est plus présent.
    if root is None and base.resolve() == PROJECT_SKILLS_DIR.resolve():
        PACKAGE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        for source in base.glob("*/SKILL.md"):
            dest = PACKAGE_SKILLS_DIR / source.parent.name / source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        (PACKAGE_SKILLS_DIR / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return out


def index_markdown(root: Optional[Path] = None) -> str:
    """Index Markdown de la bibliothèque (lisible par un agent ou un humain)."""
    skills = load_all(root)
    lines = ["# Bibliothèque de skills — ShortsForge", ""]
    lines.append(f"{len(skills)} skills disponibles. Chaque skill est autonome : on peut l'injecter")
    lines.append("tel quel dans n'importe quel agent pour exécuter sa méthode.\n")
    lines.append("| # | Skill | ID | Rôle | Version |")
    lines.append("| --- | --- | --- | --- | --- |")
    for i, s in enumerate(skills, 1):
        lines.append(f"| {i} | **{s.name}** | `{s.id}` | {s.description} | v{s.version} |")
    lines.append("")
    lines.append("## Chaîne de production recommandée\n")
    chain = [
        ("hook-architect", "Trouver l'accroche qui bloque le scroll"),
        ("script-compiler", "Écrire le script en 15-45 s"),
        ("rhythm-director", "Découper en plans de 1,5 à 3 s"),
        ("broll-curator", "Choisir les plans d'illustration"),
        ("caption-artist", "Poser les sous-titres mot par mot"),
        ("audio-mixmaster", "Mixer voix, musique et SFX"),
        ("loop-engineer", "Refermer la boucle"),
        ("cta-converter", "Convertir l'attention en action"),
        ("variant-lab", "Produire les variantes A/B"),
        ("perf-analyst", "Lire les métriques et corriger"),
    ]
    for i, (sid, role) in enumerate(chain, 1):
        exists = any(s.id == sid for s in skills)
        mark = "" if exists else " *(à installer)*"
        lines.append(f"{i}. `{sid}`{mark} — {role}")
    lines.append("")
    lines.append("## Utilisation\n")
    lines.append("```bash")
    lines.append("sf skills list          # index")
    lines.append("sf skills show <id>     # contenu d'un skill")
    lines.append("sf brief --skills a,b   # brief de production composé")
    lines.append("sf skills prompt --skills a,b  # prompt prêt à coller dans un agent")
    lines.append("```")
    return "\n".join(lines)


def compose(skill_ids: Sequence[str], *, root: Optional[Path] = None, context: str = "") -> str:
    """Compose un brief de production à partir des skills sélectionnés."""
    skills = [get(sid, root) for sid in skill_ids]
    lines = [
        "# Brief de production — Short vertical 9:16",
        "",
        f"**Skills activés :** {', '.join(s.id for s in skills)}",
        "",
        "> Objectif : un Short de 15 à 45 s, vertical 1080x1920, hook < 3 s, plans de 1,5 à 3 s,",
        "> sous-titres mot par mot, voix duckée sur une musique tendance, CTA et boucle invisible.",
        "",
    ]
    if context:
        lines += [f"**Contexte :** {context.strip()}", ""]
    for i, skill in enumerate(skills, 1):
        lines += [f"---", "", f"## {i}. {skill.name}", ""]
        if skill.when_to_use:
            lines += [f"*{skill.when_to_use}*", ""]
        lines += [skill.body.strip(), ""]
        if skill.checklist:
            lines += ["**Checklist de sortie**", ""]
            lines += [f"- [ ] {c}" for c in skill.checklist]
            lines += [""]
    return "\n".join(lines)


def as_prompt(skill_ids: Sequence[str], *, root: Optional[Path] = None) -> str:
    """Prompt compact à coller dans un agent."""
    skills = [get(sid, root) for sid in skill_ids]
    parts = [
        "Tu es un directeur artistique de Shorts marketing. Applique strictement les skills suivants.",
        "",
    ]
    parts += [s.as_prompt() for s in skills]
    parts += [
        "",
        "## Livrable attendu",
        "",
        "1. Un script minuté (0-3 s hook, 3-45 s corps, CTA final).",
        "2. Un plan de montage : plan / durée / source / mouvement / overlay.",
        "3. Une liste de sous-titres avec timecodes de début et de fin.",
        "4. Une liste de bruitages avec timecodes.",
        "5. Un JSON `ShortSpec` compatible ShortsForge.",
    ]
    return "\n".join(parts)
