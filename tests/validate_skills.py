#!/usr/bin/env python3
"""Valide les SKILL.md et l'intégrité du pack (utilisable en CI).

Contrôles :
  - frontmatter YAML présent, `name`/`description` obligatoires, `name` = dossier ;
  - description entre 40 et 1024 caractères ;
  - section d'en-tête, au moins 4 sections `##` ;
  - chaque commande `python3 .../scripts/x.py` référencée existe ;
  - chaque script possède un shebang et répond à `--help` ;
  - fichiers de données JSON valides.

Usage :
  python3 tests/validate_skills.py [--help-check] [--root CHEMIN]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_KEYS = ("name", "description", "license")
EXPECTED_SKILLS = 19
SCRIPT_RE = re.compile(
    r"(?:python3?|python)\s+([\w./~-]*(?:skills/)?[\w./-]+\.py)"
)
# formes acceptées : `scripts/x.py` (depuis le dossier du skill) ou `skills/<skill>/scripts/x.py`


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")

    def show(self) -> int:
        for warning in self.warnings:
            print(f"  ⚠️  {warning}")
        for error in self.errors:
            print(f"  ❌ {error}")
        if self.errors:
            print(f"\n{len(self.errors)} erreur(s), {len(self.warnings)} avertissement(s)")
            return 1
        print(f"\n✅ Pack valide ({len(self.warnings)} avertissement(s))")
        return 0


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Analyse un frontmatter YAML plat (clé: valeur), sans dépendance PyYAML."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4:]
    data: dict[str, str] = {}
    key = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][\w-]*\s*:", raw):
            key, value = raw.split(":", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
        elif key and raw.startswith((" ", "\t")):
            data[key] = (data[key] + " " + raw.strip()).strip()
    return data, body


def check_skill(skill_dir: Path, report: Report, help_check: bool) -> None:
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        report.error(name, "SKILL.md manquant")
        return
    text = skill_md.read_text(encoding="utf-8")
    front, body = parse_frontmatter(text)
    if not front:
        report.error(name, "frontmatter YAML absent ou non terminé par ---")
        return

    for key in REQUIRED_KEYS:
        if key not in front or not front[key]:
            report.error(name, f"clé '{key}' absente du frontmatter")
    if front.get("name") and front["name"] != name:
        report.error(name, f"name '{front['name']}' != nom du dossier '{name}'")
    description = front.get("description", "")
    if description and not (40 <= len(description) <= 1024):
        report.error(name, f"description de {len(description)} caractères (attendu 40–1024)")
    if "license" in front and front["license"].upper() != "MIT":
        report.warn(name, f"licence '{front['license']}' (MIT attendu)")

    sections = re.findall(r"^##\s+(.+)$", body, flags=re.MULTILINE)
    if len(sections) < 4:
        report.error(name, f"{len(sections)} sections '##' (minimum 4)")
    if not any("quand" in section.lower() for section in sections):
        report.warn(name, "section « Quand l'utiliser » absente")
    has_quickstart = any("démarrage" in section.lower() or "quick" in section.lower()
                         for section in sections)
    if not has_quickstart and "```bash" not in body[:3000]:
        report.warn(name, "aucun démarrage rapide (section ou commande en tête)")

    # commandes citées
    referenced_scripts: set[str] = set()
    for match in SCRIPT_RE.finditer(text):
        referenced = match.group(1)
        referenced_scripts.add(Path(referenced).name)
        if "skills/" in referenced:
            candidate = skill_dir.parent / referenced.split("skills/", 1)[-1]
        elif referenced.startswith("scripts/"):
            candidate = skill_dir / referenced
        else:
            continue
        if not candidate.exists():
            report.error(name, f"script cité introuvable : {referenced}")

    scripts = sorted((skill_dir / "scripts").glob("*.py"))
    if not scripts:
        report.error(name, "aucun script dans scripts/")
    for script in scripts:
        first_line = script.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        if not first_line or not first_line[0].startswith("#!"):
            report.warn(name, f"{script.name} sans shebang")
        if help_check:
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                capture_output=True, text=True, timeout=60,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONIOENCODING": "utf-8"},
            )
            if result.returncode != 0:
                report.error(name, f"{script.name} --help échoue ({result.returncode})")
            elif "usage:" not in (result.stdout + result.stderr).lower():
                report.error(name, f"{script.name} --help ne produit pas d'usage")

    for data_file in skill_dir.glob("*.json"):
        try:
            json.loads(data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(name, f"{data_file.name} JSON invalide : {exc}")

    # le SKILL.md doit décrire les scripts réellement présents
    for script in scripts:
        if script.name not in referenced_scripts:
            report.warn(name, f"{script.name} n'est cité dans aucune commande du SKILL.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valide les skills VESK")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--help-check", action="store_true",
                        help="exécute chaque script avec --help")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    skills_dir = root / "skills"
    report = Report()
    if not skills_dir.is_dir():
        report.error("skills/", "dossier absent")
        return report.show()

    skill_dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir())
    print(f"▸ {len(skill_dirs)} skill(s) détecté(s) dans {skills_dir}")
    if len(skill_dirs) != EXPECTED_SKILLS:
        report.warn("skills/", f"{len(skill_dirs)} skills (valeur attendue : {EXPECTED_SKILLS})")
    for skill_dir in skill_dirs:
        check_skill(skill_dir, report, args.help_check)

    readme = root / "README.md"
    if not readme.exists() or len(readme.read_text(encoding="utf-8")) < 500:
        report.error("README.md", "absent ou trop court")
    else:
        readme_text = readme.read_text(encoding="utf-8")
        for skill_dir in skill_dirs:
            if skill_dir.name not in readme_text:
                report.warn("README.md", f"{skill_dir.name} non mentionné")

    for extra in ("scripts/install.sh", "scripts/install.ps1", "LICENSE",
                  "docs/TROUBLESHOOTING.md", "examples/transcript-example.srt"):
        if not (root / extra).exists():
            report.error(extra, "fichier attendu manquant")

    return report.show()


if __name__ == "__main__":
    raise SystemExit(main())
