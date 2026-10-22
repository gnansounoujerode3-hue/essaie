"""Découverte de skills d'agent : recherche locale et écosystème skills.sh.

Deux niveaux, dans l'ordre :

1. **Local d'abord** — on scanne les skills déjà présents (dépôt, ``~/.claude/skills``
   et variantes) en lisant leur ``SKILL.md``. Hors ligne, stdlib uniquement.
2. **En ligne ensuite** — on prépare (ou on exécute) les commandes de la Skills CLI
   officielle (``npx skills find`` / ``npx skills add``) qui interroge skills.sh.

La partie en ligne ne réimplémente pas le protocole de skills.sh : elle délègue à
``npx skills``, exactement comme le skill amont ``find-skills`` (vercel-labs/skills).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import SkillError, normalize_text, read_json, skill_data

DEFAULT_CATALOG = skill_data("find-skills", "sources.json")

LEADERBOARD_URL = "https://skills.sh/"

# Mots vides FR/EN écartés lors du scoring d'une recherche locale.
STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux", "et",
    "pour", "avec", "sur", "dans", "est", "qui", "que", "comment", "faire",
    "trouve", "trouver", "cherche", "existe", "the", "a", "an", "for", "to",
    "of", "how", "do", "i", "can", "you", "find", "skill", "skills",
}


# ---------------------------------------------------------------------------
# Lecture des SKILL.md
# ---------------------------------------------------------------------------

def parse_skill_md(text: str) -> dict[str, str]:
    """Extrait le frontmatter YAML plat d'un SKILL.md (sans dépendance PyYAML).

    Gère les valeurs entre guillemets et les lignes de continuation indentées
    (descriptions longues). Les sous-clés (``metadata:``) sont aplaties en texte.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    key: str | None = None
    for raw in text[3:end].strip("\n").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][\w-]*\s*:", raw):
            key, value = raw.split(":", 1)
            key = key.strip()
            data[key] = value.strip().strip('"').strip("'")
        elif key and raw.startswith((" ", "\t")):
            data[key] = (data[key] + " " + raw.strip()).strip()
    return data


def read_skill_dir(skill_dir: Path, root: Path) -> dict[str, Any] | None:
    """Lit un dossier de skill ; retourne ``None`` s'il n'a pas de SKILL.md exploitable."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        front = parse_skill_md(skill_md.read_text(encoding="utf-8-sig", errors="replace"))
    except OSError:
        return None
    name = front.get("name") or skill_dir.name
    return {
        "name": name,
        "description": front.get("description", ""),
        "path": str(skill_dir),
        "root": str(root),
    }


# ---------------------------------------------------------------------------
# Découverte locale
# ---------------------------------------------------------------------------

def default_roots(extra: Iterable[str | Path] = ()) -> list[Path]:
    """Dossiers susceptibles de contenir des skills, du plus spécifique au plus général."""
    here = Path(__file__).resolve()
    home = Path.home()
    cwd = Path.cwd()
    candidates: list[Path] = [Path(item) for item in extra]
    candidates += [
        here.parents[2] / "skills",   # dépôt : <repo>/skills
        here.parents[3],               # installé : ~/.claude/skills (parent du skill)
        cwd / "skills",
        cwd / ".agents" / "skills",
        cwd / ".claude" / "skills",
        home / ".claude" / "skills",
        home / ".agents" / "skills",
        home / ".config" / "agents" / "skills",
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        if key not in seen:
            seen.add(key)
            roots.append(candidate)
    return roots


def discover_local_skills(roots: Sequence[Path] | None = None) -> list[dict[str, Any]]:
    """Scanne les racines et retourne les skills trouvés (premier exemplaire par nom)."""
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in (roots if roots is not None else default_roots()):
        if not root.is_dir():
            continue
        for skill_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            info = read_skill_dir(skill_dir, root)
            if info and info["name"] not in seen:
                seen.add(info["name"])
                skills.append(info)
    return sorted(skills, key=lambda item: item["name"])


# ---------------------------------------------------------------------------
# Recherche locale (scoring lexical, insensible aux accents)
# ---------------------------------------------------------------------------

def _tokens(text: str) -> list[str]:
    words = normalize_text(text).replace("-", " ").split()
    return [word for word in words if len(word) >= 2 and word not in STOPWORDS]


def search_local_skills(
    query: str,
    skills: Sequence[dict[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Classe les skills locaux par pertinence vis-à-vis du besoin exprimé."""
    tokens = _tokens(query)
    if not tokens:
        return []
    phrase = normalize_text(query)
    scored: list[dict[str, Any]] = []
    for skill in skills:
        name_text = normalize_text(skill["name"]).replace("-", " ")
        desc_text = normalize_text(skill.get("description", ""))
        score = 0
        for token in tokens:
            if token in name_text.split():
                score += 3
            if token in desc_text:
                score += 1
        if phrase and phrase in name_text:
            score += 5
        elif phrase and phrase in desc_text:
            score += 2
        if score:
            scored.append({**skill, "score": score})
    scored.sort(key=lambda item: (-item["score"], item["name"]))
    return scored[:limit]


# ---------------------------------------------------------------------------
# Catalogue (sources de confiance, catégories, critères qualité)
# ---------------------------------------------------------------------------

def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    data = read_json(Path(path) if path else DEFAULT_CATALOG)
    if "categories" not in data:
        raise SkillError("Catalogue find-skills invalide (clé 'categories' absente).")
    return data


def match_categories(need: str, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Catégories dont au moins un mot-clé apparaît dans le besoin."""
    text = normalize_text(need)
    matched = []
    for category in catalog.get("categories", []):
        if any(normalize_text(keyword) in text for keyword in category.get("keywords", [])):
            matched.append(category)
    return matched


def suggest_queries(need: str, catalog: dict[str, Any], *, limit: int = 5) -> list[str]:
    """Requêtes skills.sh (l'anglais y donne de meilleurs résultats) déduites du besoin."""
    queries: list[str] = []
    for category in match_categories(need, catalog):
        queries.extend(category.get("queries", []))
    cleaned = " ".join(_tokens(need))
    if cleaned:
        queries.append(cleaned)
    unique: list[str] = []
    for query in queries:
        if query not in unique:
            unique.append(query)
    return unique[:limit]


# ---------------------------------------------------------------------------
# Skills CLI (npx skills)
# ---------------------------------------------------------------------------

def find_command(query: str, *, owner: str | None = None) -> str:
    command = f"npx skills find {query}".strip()
    if owner:
        command += f" --owner {owner}"
    return command


def add_command(package: str, *, global_install: bool = True, yes: bool = True) -> str:
    command = f"npx skills add {package}"
    if global_install:
        command += " -g"
    if yes:
        command += " -y"
    return command


def skills_cli_available() -> bool:
    return shutil.which("npx") is not None


def run_skills_cli(arguments: Sequence[str], *, dry_run: bool = False) -> int:
    """Exécute ``npx skills …`` dans le terminal courant (ou affiche la commande)."""
    display = "npx skills " + " ".join(arguments)
    if dry_run:
        print(f"[dry-run] {display}")
        return 0
    if not skills_cli_available():
        raise SkillError(
            "npx introuvable : la recherche en ligne exige Node.js (https://nodejs.org). "
            f"Commande à lancer ensuite : {display}"
        )
    print(f"▸ {display}")
    result = subprocess.run(["npx", "skills", *arguments], check=False)
    return result.returncode


# ---------------------------------------------------------------------------
# Plan de recherche complet
# ---------------------------------------------------------------------------

def build_search_plan(
    need: str,
    *,
    catalog: dict[str, Any] | None = None,
    skills: Sequence[dict[str, Any]] | None = None,
    owner: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Assemble le plan : correspondances locales, commandes en ligne, garde-fous."""
    if not need or not need.strip():
        raise SkillError("Décris le besoin (ex. : « sous-titres animés », « react performance »).")
    catalog = catalog if catalog is not None else load_catalog()
    local = list(skills) if skills is not None else discover_local_skills()
    queries = suggest_queries(need, catalog, limit=limit)
    return {
        "need": need.strip(),
        "local_matches": search_local_skills(need, local, limit=limit),
        "local_total": len(local),
        "leaderboard": catalog.get("leaderboard", LEADERBOARD_URL),
        "categories": [category.get("id") for category in match_categories(need, catalog)],
        "online_commands": [find_command(query, owner=owner) for query in queries],
        "trusted_sources": catalog.get("trusted_sources", []),
        "quality_checklist": catalog.get("quality_checklist", []),
        "install_template": add_command("<propriétaire>/<dépôt>@<skill>"),
        "create_own": f"npx skills init {normalize_text(need).replace(' ', '-') or 'mon-skill'}",
        "npx_available": skills_cli_available(),
    }


def plan_markdown(plan: dict[str, Any]) -> str:
    lines = [f"# Recherche de skill — {plan['need']}", ""]
    lines.append("## 1. Déjà disponible localement")
    lines.append("")
    if plan["local_matches"]:
        for match in plan["local_matches"]:
            lines.append(f"- **{match['name']}** (score {match['score']}) — {match['description']}")
            lines.append(f"  `{match['path']}`")
    else:
        lines.append(f"Aucune correspondance parmi les {plan['local_total']} skill(s) locaux.")
    lines += [
        "",
        "## 2. Chercher en ligne (skills.sh)",
        "",
        f"D'abord le classement des skills les plus installés : {plan['leaderboard']}",
        "",
        "```bash",
    ]
    lines.extend(plan["online_commands"] or ["npx skills find"])
    lines += ["```", "", "## 3. Vérifier avant de recommander", ""]
    for check in plan["quality_checklist"]:
        lines.append(f"- {check}")
    lines += [
        "",
        "Sources de confiance : "
        + ", ".join(f"`{src.get('repo', src.get('name', ''))}`" for src in plan["trusted_sources"]),
        "",
        "## 4. Installer le skill retenu",
        "",
        "```bash",
        plan["install_template"],
        "```",
        "",
        "`-g` = installation globale (niveau utilisateur), `-y` = sans confirmation.",
        "",
        "## 5. Si rien n'existe",
        "",
        "Aider directement avec les capacités générales, ou créer un skill maison :",
        "",
        "```bash",
        plan["create_own"],
        "```",
        "",
    ]
    if not plan["npx_available"]:
        lines.append("> ⚠️ `npx` introuvable sur cette machine : installer Node.js pour la recherche en ligne.")
        lines.append("")
    return "\n".join(lines)
