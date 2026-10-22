#!/usr/bin/env python3
"""Trouve un skill d'agent : d'abord en local, ensuite sur skills.sh (npx skills)."""

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

from vesk.cli import base_parser, main_guard, save_or_print_json, save_text  # noqa: E402
from vesk.skillfinder import (build_search_plan, default_roots,  # noqa: E402
                              discover_local_skills, load_catalog, plan_markdown,
                              run_skills_cli, skills_cli_available,
                              suggest_queries)


def run() -> int:
    parser = base_parser(
        "Découverte de skills d'agent : recherche locale (SKILL.md déjà présents) "
        "puis écosystème skills.sh via la Skills CLI (npx skills).",
        epilog="Exemples :\n"
               "  find_skills.py \"sous-titres animés\"\n"
               "  find_skills.py \"react performance\" --md plan.md --json plan.json\n"
               "  find_skills.py \"pr review\" --online\n"
               "  find_skills.py --install vercel-labs/agent-skills@react-best-practices\n"
               "  find_skills.py --list-local\n"
               "  find_skills.py --list-categories",
    )
    parser.add_argument("need", nargs="*", help="Le besoin, en clair (ex. : « montage vidéo », « changelog »)")
    parser.add_argument("--online", action="store_true",
                        help="Exécute aussi « npx skills find … » (Node.js requis)")
    parser.add_argument("--owner", help="Restreint la recherche en ligne à un propriétaire GitHub")
    parser.add_argument("--install", metavar="PAQUET",
                        help="Installe un skill : propriétaire/dépôt@skill (via npx skills add)")
    parser.add_argument("--project", action="store_true",
                        help="Avec --install : installation projet au lieu de globale (-g)")
    parser.add_argument("--list-local", action="store_true",
                        help="Liste les skills déjà présents localement")
    parser.add_argument("--list-categories", action="store_true",
                        help="Liste les catégories de recherche et leurs requêtes types")
    parser.add_argument("--list-sources", action="store_true",
                        help="Liste les sources de confiance du catalogue")
    parser.add_argument("--root", action="append", default=[],
                        help="Dossier de skills supplémentaire à scanner (répétable)")
    parser.add_argument("--catalog", help="Catalogue JSON alternatif (défaut : sources.json du skill)")
    parser.add_argument("--limit", type=int, default=5, help="Nombre maximal de résultats/commandes")
    parser.add_argument("--json", help="Écrit le plan de recherche en JSON")
    parser.add_argument("--md", help="Écrit le plan de recherche en Markdown")
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche les commandes npx sans les exécuter")
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    roots = default_roots(args.root)

    if args.list_categories:
        for category in catalog["categories"]:
            queries = ", ".join(category.get("queries", []))
            print(f"  {category['id']:<14} {category.get('label', '')} — requêtes : {queries}")
        return 0

    if args.list_sources:
        for source in catalog.get("trusted_sources", []):
            print(f"  {source.get('repo', ''):<38} {source.get('note', '')}")
        print(f"\nClassement complet : {catalog.get('leaderboard', 'https://skills.sh/')}")
        return 0

    if args.install:
        command = ["add", args.install]
        if not args.project:
            command.append("-g")
        command.append("-y")
        return run_skills_cli(command, dry_run=args.dry_run)

    skills = discover_local_skills(roots)
    if args.list_local:
        if not skills:
            print("Aucun skill local trouvé. Dossiers scannés :")
            for root in roots:
                print(f"  - {root}")
            return 0
        print(f"{len(skills)} skill(s) local(aux) :")
        for skill in skills:
            print(f"  {skill['name']:<36} {skill['path']}")
        return 0

    need = " ".join(args.need).strip()
    if not need:
        parser.error("décris le besoin (ex. : find_skills.py \"sous-titres animés\") ou --list-local")

    plan = build_search_plan(need, catalog=catalog, skills=skills,
                             owner=args.owner, limit=args.limit)

    print(f"Besoin : {plan['need']}\n")
    if plan["local_matches"]:
        print(f"Déjà disponible localement ({plan['local_total']} skill(s) scanné(s)) :")
        for match in plan["local_matches"]:
            print(f"  ✓ {match['name']} (score {match['score']})")
            print(f"    {match['description'][:160]}")
            print(f"    {match['path']}")
        print("\nPense à utiliser un skill local avant d'en installer un nouveau.")
    else:
        print(f"Aucune correspondance parmi les {plan['local_total']} skill(s) locaux.")

    print(f"\nRecherche en ligne — classement d'abord : {plan['leaderboard']}")
    for command in plan["online_commands"]:
        print(f"  {command}")
    print("\nAvant de recommander un résultat, vérifier :")
    for check in plan["quality_checklist"]:
        print(f"  - {check}")
    print(f"\nInstallation du skill retenu : {plan['install_template']}")
    print(f"Si rien n'existe : aider directement, ou créer un skill ({plan['create_own']}).")
    if not skills_cli_available():
        print("\n⚠️  npx introuvable : installer Node.js pour exécuter les commandes ci-dessus.")

    if args.json:
        save_or_print_json(plan, args.json)
    if args.md:
        save_text(plan_markdown(plan), args.md)

    if args.online:
        queries = suggest_queries(need, catalog, limit=args.limit)
        online_args = ["find", *(queries[0].split() if queries else need.split())]
        if args.owner:
            online_args += ["--owner", args.owner]
        return run_skills_cli(online_args, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
