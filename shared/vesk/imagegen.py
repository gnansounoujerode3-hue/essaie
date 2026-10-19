"""Prompts et payloads de génération d'images/vidéos IA (Midjourney, Runway, Luma, Sora…)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from .common import SkillError, read_json, skill_data, slugify

DEFAULT_PROVIDERS = skill_data("ai-image-video-generator", "providers.json")


def load_providers(path: str | Path | None = None) -> dict[str, Any]:
    return read_json(Path(path) if path else DEFAULT_PROVIDERS)


def build_prompt(
    subject: str,
    *,
    provider: str = "midjourney",
    action: str = "",
    setting: str = "",
    camera: str = "plan rapproché, léger push-in",
    lighting: str = "lumière naturelle douce",
    style: str = "cinématographique, réaliste, contraste élevé",
    palette: str = "tons chauds, jaune et noir",
    mood: str = "intense et motivant",
    shot_type: str = "broll",
    aspect: str = "9:16",
    negative: str = "texte illisible, mains déformées, visage déformé, logo, watermark",
    motion: str = "mouvement lent et stable",
    duration: float = 5.0,
) -> dict[str, Any]:
    providers = load_providers()
    if provider not in providers["providers"]:
        raise SkillError(f"Provider inconnu : {provider} "
                         f"({', '.join(providers['providers'])})")
    meta = providers["providers"][provider]
    shot_hint = providers["shot_types"].get(shot_type, "")
    parts = [subject]
    if action:
        parts.append(action)
    if setting:
        parts.append(setting)
    if camera:
        parts.append(camera)
    if lighting:
        parts.append(lighting)
    if style:
        parts.append(style)
    if palette:
        parts.append(palette)
    if mood:
        parts.append(mood)
    core = ", ".join(part.strip(" ,.") for part in parts if part)

    if provider == "midjourney":
        prompt = (f"{core} --ar {aspect} --v 6.1 --style raw "
                  f"--no {negative}")
        params = {"aspect_ratio": aspect, "version": "6.1", "style": "raw"}
    elif provider in {"runway", "luma", "sora", "kling", "pika"}:
        prompt = (
            f"{core}. {shot_hint}. Mouvement : {motion}. "
            f"Durée prévue : {duration:.0f}s, format vertical {aspect}, "
            "aucun texte à l'écran, aucune incrustation."
        )
        params = {
            "aspect_ratio": aspect,
            "duration": duration,
            "motion": motion,
            "shot_type": shot_type,
        }
        if provider == "runway":
            params.update({"ratio": "720:1280" if aspect in {"9:16", "720:1280"} else aspect,
                           "model": "gen4.5"})
        if provider == "luma":
            params.update({"model": "ray-2", "loop": False})
    else:
        prompt = f"{core}. {shot_hint}."
        params = {"aspect_ratio": aspect, "negative_prompt": negative}

    return {
        "provider": provider,
        "provider_label": meta["label"],
        "kind": meta["kind"],
        "negative_prompt": negative,
        "prompt": prompt,
        "params": params,
        "shot_type": shot_type,
        "aspect_ratio": aspect,
        "duration": duration,
        "notes": meta["how_to"],
        "docs": meta["docs"],
    }


def build_request(provider: str, prompt: str, *, aspect: str = "9:16",
                  duration: float = 5.0, image_path: str | None = None) -> dict[str, Any]:
    """Payload API + commande curl (Runway/Luma) prête à l'emploi."""
    providers = load_providers()["providers"]
    if provider not in providers:
        raise SkillError(f"Provider inconnu : {provider}")
    meta = providers[provider]
    if not meta.get("endpoint"):
        raise SkillError(
            f"{meta['label']} n'expose pas d'API officielle publique dans ce kit. "
            f"Utilise le prompt fourni : {meta['how_to']}"
        )
    if provider == "runway":
        payload = {
            "model": "gen4.5",
            "promptText": prompt,
            "ratio": "720:1280" if aspect == "9:16" else aspect,
            "duration": int(duration),
        }
        if image_path:
            payload["promptImage"] = image_path
            endpoint = "https://api.dev.runwayml.com/v1/image_to_video"
        else:
            endpoint = meta["endpoint"]
        headers = {
            "Authorization": "Bearer $RUNWAY_API_KEY",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }
    elif provider == "luma":
        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect,
            "loop": False,
            "model": "ray-2",
        }
        endpoint = meta["endpoint"]
        headers = {
            "Authorization": "Bearer $LUMAAI_API_KEY",
            "Content-Type": "application/json",
        }
    else:
        payload = {"prompt": prompt, "aspect_ratio": aspect}
        endpoint = meta["endpoint"]
        headers = {"Authorization": "Bearer $" + meta.get("env", "API_KEY"),
                   "Content-Type": "application/json"}
    curl = (
        f"curl -X POST {endpoint} \\\n"
        + "".join(f"  -H '{key}: {value}' \\\n" for key, value in headers.items())
        + f"  -d '{json.dumps(payload, ensure_ascii=False)}'"
    )
    return {
        "provider": provider,
        "endpoint": endpoint,
        "headers": headers,
        "payload": payload,
        "curl": curl,
        "polling": _polling_help(provider),
    }


def _polling_help(provider: str) -> str:
    if provider == "luma":
        return ("GET https://api.lumalabs.ai/dream-machine/v1/generations/{id} "
                "jusqu'à state=completed, puis télécharger assets.video.")
    if provider == "runway":
        return ("GET https://api.dev.runwayml.com/v1/tasks/{id} avec les mêmes en-têtes "
                "jusqu'à status=SUCCEEDED, puis output[0].")
    return "Consulte la documentation du provider pour le suivi de tâche."


def shot_plan(
    transcript: dict[str, Any],
    *,
    provider: str = "runway",
    every: float = 8.0,
    max_shots: int = 20,
    style: str = "cinématographique, réaliste",
    aspect: str = "9:16",
    duration: float = 5.0,
) -> list[dict[str, Any]]:
    """Plan de génération : une proposition de visuel IA toutes les N secondes."""
    from .assets import query_from_text
    from .transcript import iter_sentences

    sentences = list(iter_sentences(transcript))
    if not sentences:
        raise SkillError("Transcription vide.")
    plan = []
    next_time = 0.0
    for sentence in sentences:
        if float(sentence["start"]) < next_time:
            continue
        query = query_from_text(sentence["text"], max_terms=5)
        prompt = build_prompt(
            query,
            provider=provider,
            action="plan d'illustration du propos",
            style=style,
            shot_type="broll",
            aspect=aspect,
            duration=duration,
        )
        plan.append({
            "start": round(float(sentence["start"]), 3),
            "end": round(float(sentence["end"]), 3),
            "text": sentence["text"],
            "query": query,
            "prompt": prompt,
        })
        next_time = float(sentence["start"]) + every
        if len(plan) >= max_shots:
            break
    return plan


def shot_plan_markdown(plan: Sequence[dict[str, Any]]) -> str:
    lines = ["# Plan de génération IA", "",
             "| # | Timecode | Durée | Sujet | Prompt |", "|---|----------|-------|-------|--------|"]
    for index, shot in enumerate(plan, start=1):
        prompt = shot["prompt"]["prompt"].replace("|", "\\|")
        if len(prompt) > 160:
            prompt = prompt[:157] + "…"
        duration = shot["end"] - shot["start"]
        lines.append(
            f"| {index} | {shot['start']:.1f}s | {duration:.1f}s | {shot['query']} | {prompt} |"
        )
    lines += ["", "## Prompts détaillés", ""]
    for index, shot in enumerate(plan, start=1):
        prompt = shot["prompt"]
        lines += [
            f"### Shot {index} — {shot['query']} ({shot['start']:.1f}s)",
            "",
            f"```text\n{prompt['prompt']}\n```",
            "",
            f"- **Provider** : {prompt['provider_label']} ({prompt['kind']})",
            f"- **Négatif** : {prompt['negative_prompt']}",
            f"- **Paramètres** : {json.dumps(prompt['params'], ensure_ascii=False)}",
            f"- **Usage** : {prompt['notes']}",
            "",
        ]
    return "\n".join(lines)


def provider_guide() -> str:
    data = load_providers()
    lines = ["# Providers d'images / vidéos IA", "",
             "| Provider | Type | API officielle | Format | Points forts |",
             "|----------|------|----------------|--------|--------------|"]
    for key, meta in data["providers"].items():
        lines.append(
            f"| {meta['label']} (`{key}`) | {meta['kind']} | "
            f"{'oui' if meta.get('official_api') else 'non'} | {meta['aspect']} | "
            f"{meta['strengths']} |"
        )
    lines += ["", "## Bonnes pratiques", "",
              "- Génère toujours en **9:16** pour Shorts/Reels/TikTok, jamais en 16:9 recadré.",
              "- Prévois **5 à 8 s** par plan : tu couperas au montage.",
              "- Demande **aucun texte à l'écran** : les sous-titres sont ajoutés par VESK.",
              "- Garde une **cohérence de palette** entre les plans générés et ton habillage.",
              "- Les plans IA ne remplacent pas une preuve réelle (visage, produit, résultat) : "
              "utilise-les pour illustrer, pas pour prouver.", ""]
    return "\n".join(lines)


def execute(request: dict[str, Any], *, poll_interval: float = 5.0,
            timeout: float = 600.0, download: bool = False,
            output_dir: str | Path = "ai-assets") -> dict[str, Any]:
    """Envoie réellement la requête (Runway/Luma) puis attend le résultat.

    Nécessite la variable d'environnement du provider (RUNWAY_API_KEY / LUMAAI_API_KEY).
    """
    import json as _json
    import os
    import time
    import urllib.error
    import urllib.request
    from pathlib import Path as _Path

    from .common import SkillError, info, slugify

    provider = request["provider"]
    providers = load_providers()["providers"]
    env_name = providers[provider].get("env")
    if not env_name:
        raise SkillError(f"{provider} n'a pas d'API officielle : utilise le prompt fourni.")
    api_key = os.environ.get(env_name)
    if not api_key:
        raise SkillError(f"Variable {env_name} manquante (clé API du provider).")
    headers = {key: value.replace(f"${env_name}", api_key)
               for key, value in request["headers"].items()}
    payload = _json.dumps(request["payload"], ensure_ascii=False).encode()
    http_request = urllib.request.Request(request["endpoint"], data=payload, method="POST",
                                          headers=headers)
    info(f"Envoi de la génération à {provider}…")
    try:
        with urllib.request.urlopen(http_request, timeout=120) as response:
            created = _json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise SkillError(f"Erreur {provider} ({exc.code}) : {detail}") from exc
    except urllib.error.URLError as exc:
        raise SkillError(f"API {provider} injoignable : {exc.reason}") from exc

    job_id = created.get("id") or created.get("taskId") or created.get("task_id")
    if not job_id:
        return {"provider": provider, "created": created, "status": "unknown"}
    if provider == "luma":
        poll_url = f"https://api.lumalabs.ai/dream-machine/v1/generations/{job_id}"
        done_states = {"completed"}
        failed_states = {"failed"}
    elif provider == "runway":
        poll_url = f"https://api.dev.runwayml.com/v1/tasks/{job_id}"
        done_states = {"SUCCEEDED"}
        failed_states = {"FAILED", "CANCELLED"}
    else:
        return {"provider": provider, "created": created, "job": job_id}

    info(f"Tâche {job_id} envoyée — attente du rendu…")
    deadline = time.time() + timeout
    state = "queued"
    result = created
    while time.time() < deadline:
        time.sleep(poll_interval)
        poll = urllib.request.Request(poll_url, headers=headers)
        try:
            with urllib.request.urlopen(poll, timeout=60) as response:
                result = _json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            raise SkillError(f"Suivi de tâche impossible ({exc.code}).") from exc
        state = str(result.get("state") or result.get("status") or "")
        if state in done_states or state in failed_states:
            break
    if state not in done_states:
        raise SkillError(f"Génération non terminée (état : {state}). Réessaie avec --timeout.")

    asset_url = None
    if provider == "luma":
        asset_url = (result.get("assets") or {}).get("video")
    elif provider == "runway":
        outputs = result.get("output") or []
        asset_url = outputs[0] if outputs else None
    output = {"provider": provider, "job": job_id, "state": state, "url": asset_url,
              "raw": result}
    if download and asset_url:
        suffix = _Path(asset_url.split("?")[0]).suffix or (".mp4" if provider != "midjourney" else ".png")
        target = _Path(output_dir) / f"{provider}-{slugify(job_id)}-{int(time.time())}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(asset_url), timeout=300) as response:
            target.write_bytes(response.read())
        output["file"] = str(target.resolve())
        info(f"Téléchargé : {target}")
    return output
