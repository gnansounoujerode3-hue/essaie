"""Bibliothèque d'accroches virales : templates, variantes et plan de hook 0-3 s."""

from __future__ import annotations

import random
import re
import string
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import SkillError, read_json, skill_data

DEFAULT_LIBRARY = skill_data("viral-hooks-library", "hooks.json")

DEFAULT_VALUES = {
    "sujet": "[ton sujet]",
    "action": "[l'action à arrêter]",
    "consequence": "[la conséquence]",
    "mythe": "[le mythe]",
    "resultat": "[le résultat]",
    "delai": "[délai]",
    "obstacle": "[l'obstacle évité]",
    "chiffre": "[chiffre]",
    "chiffre2": "[chiffre]",
    "tache": "[la tâche chronophage]",
    "public": "[le public]",
    "probleme": "[le problème]",
    "benefice": "[le bénéfice]",
    "adversaire": "[l'adversaire]",
    "evenement": "[l'événement]",
    "cout": "[le coût]",
    "unite": "[unité]",
}


def load_library(path: str | Path | None = None) -> dict[str, Any]:
    data = read_json(Path(path) if path else DEFAULT_LIBRARY)
    if "templates" not in data:
        raise SkillError("Bibliothèque de hooks invalide (clé 'templates' absente).")
    return data


def categories(library: dict[str, Any]) -> dict[str, str]:
    return dict(library.get("categories", {}))


def select_templates(
    library: dict[str, Any],
    *,
    category: str | None = None,
    platform: str | None = None,
    query: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    templates = list(library.get("templates", []))
    if category:
        templates = [t for t in templates if t.get("category") == category]
    if platform:
        templates = [t for t in templates if platform in t.get("platforms", [])]
    if query:
        needle = query.lower()
        templates = [
            t for t in templates
            if needle in (t.get("name", "") + " " + t.get("template", "") + " "
                          + t.get("example", "")).lower()
        ]
    if limit:
        templates = templates[:limit]
    return templates


def fill(template: str, values: dict[str, str]) -> str:
    fmt = string.Formatter()
    class SafeDict(dict):
        def __missing__(self, key: str) -> str:
            return str(values.get(key, DEFAULT_VALUES.get(key, f"[{key}]")))
    try:
        return fmt.vformat(template, (), SafeDict(values))
    except (ValueError, KeyError) as exc:
        raise SkillError(f"Template invalide : {template} ({exc})") from exc


def generate_variants(
    topic: str,
    library: dict[str, Any],
    *,
    count: int = 5,
    category: str | None = None,
    platform: str | None = None,
    values: dict[str, str] | None = None,
    seed: int = 7,
) -> list[dict[str, Any]]:
    merged = dict(DEFAULT_VALUES)
    merged["sujet"] = topic
    merged.update({key: value for key, value in (values or {}).items() if value})
    templates = select_templates(library, category=category, platform=platform)
    if not templates:
        raise SkillError("Aucun template ne correspond à ces filtres.")
    rng = random.Random(seed)
    if len(templates) <= count:
        chosen = templates
    else:
        by_category: dict[str, list[dict[str, Any]]] = {}
        for template in templates:
            by_category.setdefault(template["category"], []).append(template)
        chosen = []
        cats = list(by_category)
        rng.shuffle(cats)
        while len(chosen) < count:
            for cat in cats:
                if len(chosen) >= count:
                    break
                bucket = by_category[cat]
                if bucket:
                    chosen.append(bucket.pop(rng.randrange(len(bucket))))
                if not any(by_category.values()):
                    break
    variants = []
    for template in chosen:
        text = fill(template["template"], merged)
        example = template.get("example", "")
        if topic and topic not in ("[ton sujet]", "") and "{sujet}" in template["template"]:
            example = ""
        variants.append({
            "template_id": template["id"],
            "name": template.get("name", template["id"]),
            "category": template.get("category"),
            "mechanic": template.get("mechanic"),
            "hook": text,
            "example": example,
            "visual": template.get("visual", ""),
            "sound": template.get("sound", ""),
            "platforms": template.get("platforms", []),
            "duration": "0 → 3 s",
            "caption": _caption(text, topic),
            "shotlist": _shotlist(template, text),
            "sfx_cue": _sfx(template.get("sound", "")),
        })
    return variants


def _caption(hook: str, topic: str) -> str:
    cleaned = re.sub(r"\s+", " ", hook).strip()
    tags = "#shorts #reels #montagevideo"
    return f"{cleaned} {tags}".strip()


def _shotlist(template: dict[str, Any], hook: str) -> list[dict[str, str]]:
    return [
        {"time": "0.0 → 1.0 s", "shot": "Visage plein cadre ou preuve à l'écran",
         "intent": hook,
         "motion": "zoom-in 104 → 100 %, coupe sur le 1er mot"},
        {"time": "1.0 → 2.2 s", "shot": template.get("visual", "insert / B-roll"),
         "intent": "matérialiser la promesse",
         "motion": "cut sec + pop de texte clé"},
        {"time": "2.2 → 3.0 s", "shot": "retour visage ou résultat",
         "intent": "ouvrir la boucle (révélation repoussée)",
         "motion": "micro-push-in, pas de transition molle"},
    ]


def _sfx(sound: str) -> list[str]:
    known = ["whoosh", "pop", "braam", "camera click", "riser", "impact", "tick",
             "glass break", "buzzer", "switch", "cash"]
    found = [name for name in known if name in sound.lower()]
    return found or ["pop", "whoosh"]


def harmonic_variants(variants: Sequence[dict[str, Any]], *, count: int = 3) -> list[dict[str, str]]:
    """3 angles complémentaires pour A/B tester le même sujet."""
    angles = [
        ("question", "Transforme le hook en question directe au spectateur."),
        ("preuve", "Ouvre sur le résultat chiffré, puis remonte le contexte."),
        ("contrarian", "Commence par « Arrête… » ou « On t'a menti… » et casse la croyance."),
    ]
    output = []
    for index, (angle, instruction) in enumerate(angles[:count]):
        base = variants[index % len(variants)] if variants else None
        output.append({
            "angle": angle,
            "instruction": instruction,
            "based_on": base["name"] if base else None,
            "hook": base["hook"] if base else "",
        })
    return output


def build_hook_plan(
    topic: str,
    library: dict[str, Any],
    *,
    platform: str = "tiktok",
    count: int = 5,
    category: str | None = None,
    values: dict[str, str] | None = None,
    seed: int = 7,
) -> dict[str, str | list[Any]]:
    variants = generate_variants(topic, library, count=count, category=category,
                                 platform=platform, values=values, seed=seed)
    primary = variants[0]
    return {
        "topic": topic,
        "platform": platform,
        "primary_hook": primary,
        "alternatives": variants[1:],
        "ab_tests": harmonic_variants(variants),
        "structure": [
            {"range": "0 → 1 s", "role": "pattern interrupt",
             "action": primary["shotlist"][0]["motion"], "sound": primary["sfx_cue"][0]},
            {"range": "1 → 3 s", "role": "promesse / boucle ouverte",
             "action": "énoncer le hook, montrer la preuve ou le résultat",
             "sound": "coupe sèche, musique absente ou très basse"},
            {"range": "3 → 8 s", "role": "contexte minimal",
             "action": "une seule phrase de contexte, pas de générique",
             "sound": "beat entre, whoosh sur la transition"},
            {"range": "8 → 20 s", "role": "première valeur",
             "action": "livrer la première information utile, couper tous les blancs",
             "sound": "SFX sur chaque apparition de texte"},
            {"range": "fin", "role": "boucle / CTA",
             "action": "revenir à la promesse du début ou enchaîner sur la vidéo suivante",
             "sound": "riser court puis silence"},
        ],
        "edit_spec": {
            "format": "9:16, 1080x1920, 30 ou 60 fps",
            "captions": "style hormozi ou karaoke-pop, 1 à 3 mots, pop à chaque mot",
            "broll": f"chercher « {topic} », « résultat », « avant après »",
            "pacing": "coupe toutes les 1,2 à 2,5 s, aucun silence > 0,3 s",
            "first_frame": "visage ou preuve, jamais un logo",
        },
        "viral_score": _viral_score(primary),
    }


def _viral_score(variant: dict[str, Any]) -> dict[str, Any]:
    hook = variant.get("hook", "").lower()
    score = 55
    reasons = []
    if re.search(r"\d", hook):
        score += 10; reasons.append("chiffre concret")
    if re.search(r"\?|comment|pourquoi", hook):
        score += 8; reasons.append("question")
    if re.search(r"arrete|personne|jamais|faux|erreur", hook):
        score += 8; reasons.append("contraste")
    if len(hook.split()) <= 14:
        score += 7; reasons.append("hook court")
    else:
        score -= 5; reasons.append("hook trop long : à raccourcir")
    if re.search(r"\b(tu|vous|ton|ta)\b", hook):
        score += 6; reasons.append("adresse directe")
    return {"score": max(0, min(100, score)), "reasons": reasons}


def hooks_markdown(plan: dict[str, Any]) -> str:
    primary = plan["primary_hook"]
    lines = [
        "# Plan de hook viral",
        "",
        f"**Sujet** : {plan['topic']} · **Plateforme** : {plan['platform']}",
        "",
        "## Hook principal (0 → 3 s)",
        "",
        f"> {primary['hook']}",
        "",
        f"- **Angle** : {primary['name']} ({primary['category']}) · mécanique *{primary['mechanic']}*",
        f"- **Score viral estimé** : {plan['viral_score']['score']}/100 — "
        f"{', '.join(plan['viral_score']['reasons'])}",
        f"- **Visuel** : {primary['visual']}",
        f"- **Son** : {primary['sound']}",
        f"- **Légende** : {primary['caption']}",
        "",
        "### Storyboard 3 secondes",
        "",
        "| Temps | Plan | Intention | Mouvement |",
        "|-------|------|-----------|-----------|",
    ]
    for shot in primary["shotlist"]:
        lines.append(f"| {shot['time']} | {shot['shot']} | {shot['intent']} | {shot['motion']} |")
    lines += ["", "## Structure complète", "", "| Temps | Rôle | Action | Son |",
              "|-------|------|--------|-----|"]
    for step in plan["structure"]:
        lines.append(f"| {step['range']} | {step['role']} | {step['action']} | {step['sound']} |")
    lines += ["", "## Variantes à tester", ""]
    for variant in plan["alternatives"]:
        lines.append(f"- **{variant['name']}** ({variant['category']}) — {variant['hook']}")
    lines += ["", "## A/B tests", ""]
    for test in plan["ab_tests"]:
        lines.append(f"- **{test['angle']}** : {test['instruction']} (base : {test['based_on']})")
    lines += ["", "## Réglages de montage", ""]
    for key, value in plan["edit_spec"].items():
        lines.append(f"- **{key}** : {value}")
    lines += [
        "",
        "> Les hooks se jugent à la **rétention des 3 premières secondes**, pas au nombre de likes. "
        "Publie la même vidéo avec 2 hooks différents et compare la courbe.",
        "",
    ]
    return "\n".join(lines)
