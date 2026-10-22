---
name: find-skills
description: Découvrir et installer des skills d'agent depuis l'écosystème ouvert (skills.sh, CLI `npx skills`), après avoir cherché dans les skills déjà installés localement. Utiliser ce skill pour « trouve un skill pour… », « est-ce qu'il existe un skill qui… », « comment faire X » quand X peut exister comme skill installable, ou « étendre les capacités de l'agent ».
license: MIT
metadata:
  version: 1.0.0
  category: decouverte
  requires: rien pour la recherche locale ; Node.js (npx) pour la recherche en ligne
---

# Trouver et installer des skills (find-skills)

Skill méta, adapté en français du skill amont **find-skills** de
[vercel-labs/skills](https://skills.sh/vercel-labs/skills/find-skills) (MIT) et augmenté
d'une recherche **locale** : avant d'installer quoi que ce soit, on vérifie que la
capacité n'existe pas déjà parmi les skills présents (ce kit en contient 20).

La **Skills CLI** (`npx skills`) est le gestionnaire de paquets de l'écosystème ouvert
des skills d'agent. Parcourir le catalogue : <https://skills.sh/>

## Quand l'utiliser

- L'utilisateur demande « comment faire X » et X est une tâche courante qui a
  probablement déjà un skill dédié.
- « Trouve un skill pour X », « il existe un skill qui fait X ? », « tu sais faire X ? »
  (capacité spécialisée).
- L'utilisateur veut étendre les capacités de l'agent, ou cherche un outil, un
  template, un workflow pour un domaine (design, tests, déploiement, montage…).

## Démarrage rapide

```bash
# Plan complet : correspondances locales + commandes en ligne + critères qualité
python3 scripts/find_skills.py "sous-titres animés"

# Ce qui est déjà installé chez toi
python3 scripts/find_skills.py --list-local

# Recherche en ligne immédiate (délègue à npx skills)
python3 scripts/find_skills.py "react performance" --online

# Installer le skill retenu (global, sans confirmation)
python3 scripts/find_skills.py --install vercel-labs/agent-skills@react-best-practices
```

## La méthode en 6 étapes

1. **Comprendre le besoin** : domaine (React, tests, montage…), tâche précise
   (écrire des tests, animer des sous-titres, relire des PR) et probabilité qu'un
   skill existe déjà.
2. **Chercher en local d'abord** : `python3 scripts/find_skills.py "<besoin>"` scanne
   les `SKILL.md` du dépôt et de `~/.claude/skills` (et variantes) et classe les
   correspondances. Un skill déjà là vaut mieux qu'une installation de plus.
3. **Consulter le classement skills.sh** : <https://skills.sh/> classe les skills par
   nombre d'installations — les options les plus éprouvées remontent en premier
   (ex. `vercel-labs/agent-skills` et `anthropics/skills`, 100K+ installations).
4. **Chercher en ligne** si besoin : `npx skills find [requête] [--owner <propriétaire>]`
   — par ex. « mon app React est lente » → `npx skills find react performance` ;
   « aide-moi pour les revues de PR » → `npx skills find pr review` ;
   « il me faut un changelog » → `npx skills find changelog`.
   L'anglais donne de meilleurs résultats : le script traduit le besoin en requêtes
   types grâce aux catégories de `sources.json`.
5. **Vérifier la qualité avant de recommander** — ne jamais recommander un skill sur
   le seul résultat de recherche :
   - **installations** : préférer 1 000+, prudence sous 100 ;
   - **source** : éditeurs reconnus (`vercel-labs`, `anthropics`, `microsoft`…) plutôt
     qu'auteurs inconnus ;
   - **étoiles GitHub** du dépôt source : sous 100, scepticisme ;
   - **lire le SKILL.md** : commandes exécutées, accès réseau, clés API demandées.
6. **Présenter puis proposer d'installer** : nom du skill, ce qu'il fait, installations
   et source, commande d'installation, lien skills.sh. Exemple :

   ```text
   J'ai trouvé un skill adapté ! « react-best-practices » fournit les règles
   d'optimisation React/Next.js de l'équipe Vercel (185K installations).

   Pour l'installer :
   npx skills add vercel-labs/agent-skills@react-best-practices

   Détails : https://skills.sh/vercel-labs/agent-skills/react-best-practices
   ```

   Installation directe (si l'utilisateur est d'accord) :
   `npx skills add <propriétaire>/<dépôt>@<skill> -g -y`
   (`-g` = globale/niveau utilisateur, `-y` = sans confirmation), ou via le script :
   `python3 scripts/find_skills.py --install <propriétaire>/<dépôt>@<skill>`.

## Catégories fréquentes

| Catégorie | Requêtes types |
|-----------|----------------|
| Vidéo & montage | video editing, ffmpeg, subtitles captions (souvent déjà dans ce kit !) |
| Développement web | react, nextjs, typescript, css, tailwind |
| Tests | testing, jest, playwright, e2e |
| DevOps | deploy, docker, kubernetes, ci-cd |
| Documentation | docs, readme, changelog, api-docs |
| Qualité de code | review, lint, refactor, best-practices |
| Design | ui, ux, design-system, accessibility |
| Productivité | workflow, automation, git |

Détail et sources de confiance : `python3 scripts/find_skills.py --list-categories`
et `python3 scripts/find_skills.py --list-sources` (données dans `sources.json`,
modifiable via `--catalog`).

## Bien chercher

1. **Mots-clés précis** : « react testing » plutôt que « testing ».
2. **Synonymes** : si « deploy » ne donne rien, essayer « deployment » ou « ci-cd ».
3. **Sources connues** : beaucoup de skills vivent dans `vercel-labs/agent-skills`
   ou `ComposioHQ/awesome-claude-skills` ; `--owner` restreint la recherche.
4. **Sorties réutilisables** : `--md plan.md` / `--json plan.json` produisent le plan
   complet (local, commandes, critères) à joindre à une réponse ou à un rapport.

## Si aucun skill n'existe

1. Le dire clairement (« aucun skill trouvé pour X »).
2. Proposer d'aider directement avec les capacités générales de l'agent.
3. Si le besoin revient souvent, suggérer de créer un skill maison :
   `npx skills init mon-skill` — dans ce kit, copier la structure d'un skill existant
   (`SKILL.md` + `scripts/` + données JSON) puis valider avec
   `python3 tests/validate_skills.py --help-check`.

## Limites

- La recherche locale est **lexicale** (nom + description des `SKILL.md`, insensible
  aux accents) : un skill mal décrit peut être manqué, un score n'est pas un jugement.
- La recherche en ligne **délègue à `npx skills`** : Node.js et un accès réseau sont
  requis ; sans `npx`, le script affiche les commandes à lancer.
- Les seuils qualité (installations, étoiles) sont des **heuristiques** de prudence,
  pas des garanties : un skill récent et excellent peut être peu installé.
- Installer un skill, c'est faire confiance à son auteur : relire son `SKILL.md` et
  ses scripts avant tout `add`, surtout hors sources officielles.

## Suite logique

Le skill fraîchement installé selon son propre `SKILL.md` ; dans ce kit, les besoins
vidéo renvoient le plus souvent à `animated-captions-generator`,
`highlight-detector-ai` ou `ffmpeg-power-tools` — déjà sur place.
