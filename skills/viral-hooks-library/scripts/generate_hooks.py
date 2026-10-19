#!/usr/bin/env python3
"""Génère des hooks viraux et un plan des 3 premières secondes."""

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

from vesk.cli import base_parser, main_guard, save_text  # noqa: E402
from vesk.common import SkillError, read_json, write_json  # noqa: E402
from vesk.hooks import (build_hook_plan, categories, generate_variants,  # noqa: E402
                        hooks_markdown, load_library, select_templates)


def run() -> int:
    parser = base_parser(
        "Bibliothèque d'accroches virales : templates, variantes, storyboard 3 s.",
        epilog="Exemples :\n"
               "  generate_hooks.py --topic \"sous-titres automatiques\" --count 6 --md hooks.md\n"
               "  generate_hooks.py --list\n"
               "  generate_hooks.py --list-category contrarian\n"
               "  generate_hooks.py --topic IA --platform tiktok --set "
               "public=\"createur\" --json plan.json",
    )
    parser.add_argument("--topic", help="Sujet de la vidéo")
    parser.add_argument("--category", help="curiosite, contrarian, resultat, histoire, probleme, "
                                          "liste, preuve, urgence, defi, comparaison")
    parser.add_argument("--platform", default="tiktok",
                        choices=["tiktok", "reels", "shorts", "youtube", "linkedin"])
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--set", action="append", default=[],
                        help="Remplit un placeholder : --set 'public=createurs'")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--library", help="Bibliothèque JSON alternative")
    parser.add_argument("--json", help="Plan JSON")
    parser.add_argument("--md", help="Plan Markdown")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--list-category", help="Affiche les templates d'une catégorie")
    args = parser.parse_args()

    library = load_library(args.library)
    if args.list:
        print("Catégories :")
        for key, label in categories(library).items():
            count = len([t for t in library["templates"] if t.get("category") == key])
            print(f"  {key:<12} {count:>2} templates — {label}")
        print("\nTemplates :")
        for template in library["templates"]:
            print(f"  {template['id']:<28} {template['name']}")
        return 0
    if args.list_category:
        for template in select_templates(library, category=args.list_category):
            print(f"## {template['name']} ({template['category']})")
            print(f"   {template['template']}")
            print(f"   visuel : {template.get('visual', '')}")
            print(f"   son    : {template.get('sound', '')}\n")
        return 0
    if not args.topic:
        parser.error("indique --topic (ou --list)")

    values = {}
    for item in args.set:
        if "=" not in item:
            raise SkillError(f"--set attend clé=valeur, reçu : {item}")
        key, value = item.split("=", 1)
        values[key.strip()] = value.strip()

    plan = build_hook_plan(args.topic, library, platform=args.platform,
                           count=args.count, category=args.category,
                           values=values, seed=args.seed)
    if args.json:
        write_json(args.json, plan)
        print(f"✅ JSON : {args.json}")
    if args.md:
        save_text(hooks_markdown(plan), args.md)
    if not args.json and not args.md:
        print(hooks_markdown(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
