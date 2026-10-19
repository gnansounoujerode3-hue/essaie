"""Bibliothèque de B-rolls : scan, recherche lexicale, recherche sémantique CLIP optionnelle."""

from __future__ import annotations

import json
import math
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import SkillError, info, normalize_text, read_json, slugify, warn, write_json
from .ffmpeg import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, extract_frame, media_info

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
ASSET_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
CACHE_NAME = ".vesk-index.json"


# --------------------------------------------------------------------------- scan


def _sidecar_text(path: Path) -> str:
    candidates = [path.with_suffix(".txt"), path.with_suffix(".json"),
                  path.parent / "meta.json", path.parent / "tags.txt"]
    for candidate in candidates:
        if candidate.exists() and candidate.suffix == ".txt":
            return candidate.read_text(encoding="utf-8", errors="replace")[:2000]
    data_file = path.parent / "meta.json"
    if data_file.exists():
        try:
            data = json.loads(data_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                entry = data.get(path.name) or data.get(path.stem)
                if isinstance(entry, dict):
                    return " ".join(str(v) for v in entry.values())[:2000]
                if isinstance(entry, str):
                    return entry[:2000]
        except json.JSONDecodeError:
            pass
    return ""


def scan(paths: Sequence[str | Path], *, recursive: bool = True,
         include_images: bool = True) -> list[dict[str, Any]]:
    allowed = set(ASSET_EXTENSIONS if include_images else VIDEO_EXTENSIONS)
    seen: set[Path] = set()
    files: list[Path] = []
    for raw in paths:
        root = Path(raw).expanduser()
        if root.is_file():
            files.append(root)
            continue
        if not root.exists():
            warn(f"Dossier introuvable, ignoré : {root}")
            continue
        iterator = root.rglob("*") if recursive else root.glob("*")
        for candidate in sorted(iterator):
            if candidate.is_file() and candidate.suffix.lower() in allowed:
                files.append(candidate)
    assets: list[dict[str, Any]] = []
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        suffix = path.suffix.lower()
        kind = "video" if suffix in VIDEO_EXTENSIONS else "image"
        entry: dict[str, Any] = {
            "path": str(resolved),
            "name": path.name,
            "stem": path.stem,
            "kind": kind,
            "ext": suffix,
            "size_bytes": path.stat().st_size,
            "tags": _tags_from_name(path.stem),
            "description": _sidecar_text(path),
        }
        if kind == "video":
            try:
                meta = media_info(path)
                entry.update({
                    "duration": meta["duration"],
                    "width": meta["width"],
                    "height": meta["height"],
                    "fps": meta["fps"],
                    "has_audio": meta["has_audio"],
                })
            except SkillError:
                entry["duration"] = 0.0
                entry["error"] = "média illisible"
        assets.append(entry)
    info(f"{len(assets)} asset(s) indexé(s).")
    return assets


def _tags_from_name(stem: str) -> list[str]:
    raw = normalize_text(re.sub(r"[_\-.]+", " ", stem))
    stop = {"the", "and", "with", "le", "la", "les", "des", "une", "and", "shot",
            "clip", "video", "final", "hd", "4k", "1080", "1920"}
    return [token for token in raw.split() if len(token) > 2 and token not in stop][:12]


def library_document(asset: dict[str, Any]) -> str:
    parts = [asset.get("name", ""), asset.get("stem", ""), " ".join(asset.get("tags", [])),
             asset.get("description", "")]
    return normalize_text(" ".join(str(p) for p in parts if p))


# --------------------------------------------------------------------------- lexical


def lexical_search(assets: Sequence[dict[str, Any]], query: str,
                   *, top_k: int = 8) -> list[dict[str, Any]]:
    terms = [t for t in normalize_text(query).split() if len(t) > 1]
    if not terms:
        return [{"asset": a, "score": 0.0} for a in assets[:top_k]]
    results = []
    for asset in assets:
        document = library_document(asset)
        tokens = set(document.split())
        score = 0.0
        for term in terms:
            if term in tokens:
                score += 1.0
            elif any(token.startswith(term) for token in tokens):
                score += 0.6
            elif term in document:
                score += 0.4
        if score:
            score += 0.05 * min(3, len(asset.get("tags", [])))
            score /= math.sqrt(max(1, len(tokens)) / 6.0)
        results.append({"asset": asset, "score": round(score, 4)})
    results.sort(key=lambda item: item["score"], reverse=True)
    return [r for r in results if r["score"] > 0][:top_k] or \
        [{"asset": a, "score": 0.0} for a in assets[:top_k]]


# --------------------------------------------------------------------------- CLIP


def _clip_available() -> bool:
    import importlib.util

    return all(importlib.util.find_spec(m) is not None
               for m in ("torch", "transformers", "PIL"))


class ClipIndex:
    """Index CLIP minimaliste (images + frames vidéo), cache JSON local."""

    MODEL = "openai/clip-vit-base-patch32"

    def __init__(self, model_name: str = MODEL):
        if not _clip_available():
            raise SkillError(
                "Recherche sémantique indisponible : installe\n"
                "  pip install torch transformers pillow\n"
                "puis relance avec --semantic (1er téléchargement du modèle CLIP)."
            )
        import torch  # type: ignore
        from transformers import CLIPModel, CLIPProcessor  # type: ignore

        self.torch = torch
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model = CLIPModel.from_pretrained(model_name)
        self.model.eval()
        self.model_name = model_name

    def embed_images(self, paths: Sequence[str | Path]) -> "Any":
        from PIL import Image  # type: ignore

        images = []
        for path in paths:
            try:
                with Image.open(path) as image:
                    images.append(image.convert("RGB").copy())
            except Exception:
                images.append(None)
        tensors = []
        batch = 8
        for index in range(0, len(images), batch):
            chunk = [img for img in images[index:index + batch] if img is not None]
            if not chunk:
                tensors.append(self.torch.zeros((0, 512)))
                continue
            inputs = self.processor(images=chunk, return_tensors="pt")
            with self.torch.no_grad():
                features = self.model.get_image_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
            tensors.append(features)
        return self.torch.cat(tensors, dim=0) if tensors else self.torch.zeros((0, 512))

    def embed_texts(self, texts: Sequence[str]) -> "Any":
        inputs = self.processor(text=list(texts), return_tensors="pt", padding=True,
                                truncation=True)
        with self.torch.no_grad():
            features = self.model.get_text_features(**inputs)
        return features / features.norm(dim=-1, keepdim=True)

    def embed_asset(self, asset: dict[str, Any]) -> list[float]:
        path = Path(asset["path"])
        if asset["kind"] == "image":
            tensor = self.embed_images([path])[0]
            return [round(float(v), 5) for v in tensor]
        samples = self._video_frames(path)
        if not samples:
            return []
        tensor = self.embed_images(samples).mean(dim=0)
        tensor = tensor / tensor.norm()
        return [round(float(v), 5) for v in tensor]

    def _video_frames(self, path: Path) -> list[Path]:
        duration = float(media_info(path).get("duration") or 0)
        times = [duration * ratio for ratio in (0.12, 0.5, 0.88)] if duration else [0.0]
        tempdir = Path(tempfile.mkdtemp(prefix="vesk-frames-"))
        frames = []
        for index, time in enumerate(times):
            target = tempdir / f"frame_{index}.jpg"
            try:
                extract_frame(path, target, time=time, width=480)
                if target.exists():
                    frames.append(target)
            except SkillError:
                continue
        return frames


def semantic_search(assets: Sequence[dict[str, Any]], query: str,
                    *, top_k: int = 8, cache_path: str | Path | None = None,
                    model_name: str = ClipIndex.MODEL) -> list[dict[str, Any]]:
    indexer = ClipIndex(model_name)
    cache = read_json(cache_path) if cache_path and Path(cache_path).exists() else {}
    vectors: list[list[float]] = []
    changed = False
    for asset in assets:
        key = f"{asset['path']}|{asset.get('size_bytes')}|{model_name}"
        vector = cache.get(key)
        if not vector:
            try:
                vector = indexer.embed_asset(asset)
            except Exception as exc:  # frame vidéo illisible, format exotique…
                warn(f"Embedding impossible pour {asset['name']} : {exc}")
                vector = []
            cache[key] = vector
            changed = True
        vectors.append(vector)
    if changed and cache_path:
        write_json(cache_path, cache)
    query_vector = indexer.embed_texts([query])[0]
    scored = []
    for asset, vector in zip(assets, vectors):
        if not vector:
            continue
        import torch  # type: ignore

        tensor = torch.tensor(vector, dtype=query_vector.dtype)
        score = float(torch.dot(tensor, query_vector))
        scored.append({"asset": asset, "score": round(score, 4)})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def search(assets: Sequence[dict[str, Any]], query: str, *, semantic: bool = False,
           top_k: int = 8, cache_path: str | Path | None = None) -> list[dict[str, Any]]:
    if semantic:
        return semantic_search(assets, query, top_k=top_k, cache_path=cache_path)
    return lexical_search(assets, query, top_k=top_k)


# --------------------------------------------------------------------------- plan B-roll


def query_from_text(text: str, *, max_terms: int = 6) -> str:
    """Extrait une requête courte (mots porteurs) d'une phrase."""
    stop = {
        "le", "la", "les", "un", "une", "des", "du", "de", "dans", "sur", "pour",
        "avec", "sans", "que", "qui", "quoi", "est", "sont", "être", "avoir", "mais",
        "donc", "alors", "comme", "plus", "moins", "très", "tout", "tous", "toute",
        "cette", "cette", "ces", "son", "sa", "ses", "leur", "leurs", "nous", "vous",
        "ils", "elles", "je", "tu", "il", "elle", "on", "et", "ou", "à", "au", "aux",
        "en", "par", "ce", "cet", "mon", "ton", "notre", "votre", "the", "and", "of",
        "to", "in", "is", "are", "you", "your", "it", "this", "that", "for", "with",
        "salut", "bonjour", "aujourd", "hui", "vais", "va", "allez", "veux", "veut",
        "peux", "peut", "sais", "sait", "montrer", "montre", "dis", "dire", "dit",
        "parle", "parler", "vois", "voir", "regarde", "prendre", "prends", "fais",
        "faire", "faut", "donc", "aussi", "encore", "vraiment", "juste", "autre",
        "chose", "choses", "gens", "personne", "fois", "peu", "bien", "bon", "bah",
        "voila", "voici", "ici", "là", "oui", "non", "alors", "après", "avant",
    }
    tokens = [t for t in normalize_text(text).split() if t not in stop and len(t) > 2]
    if not tokens:
        tokens = normalize_text(text).split()
    return " ".join(tokens[:max_terms])


def plan_broll(
    transcript: dict[str, Any],
    assets: Sequence[dict[str, Any]],
    *,
    semantic: bool = False,
    min_clip: float = 2.0,
    max_clip: float = 5.0,
    top_k: int = 5,
    reuse: bool = False,
    cache_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    from .transcript import iter_sentences, trim_to_range

    if not assets:
        raise SkillError("Bibliothèque B-roll vide.")
    used: set[str] = set()
    plan: list[dict[str, Any]] = []
    rotating = 0
    for sentence in iter_sentences(transcript):
        duration = float(sentence["end"]) - float(sentence["start"])
        if duration < 1.0:
            continue
        query = query_from_text(sentence["text"])
        candidates = search(assets, query, semantic=semantic, top_k=max(1, top_k),
                            cache_path=cache_path)
        choice = None
        for candidate in candidates:
            asset = candidate["asset"]
            if candidate["score"] <= 0:
                continue
            if not reuse and asset["path"] in used:
                continue
            if asset.get("duration") and float(asset["duration"]) < 1.0:
                continue
            choice = candidate
            break
        if choice is None:
            available = [a for a in assets
                         if reuse or a["path"] not in used or len(used) >= len(assets)]
            if not available:
                available = list(assets)
            chosen = available[rotating % len(available)]
            rotating += 1
            choice = {"asset": chosen, "score": 0.0}
        used.add(choice["asset"]["path"])
        clip_len = round(min(max(duration * 0.55, min_clip), max_clip), 2)
        if choice["asset"].get("duration"):
            clip_len = min(clip_len, float(choice["asset"]["duration"]))
        plan.append({
            "start": round(float(sentence["start"]), 3),
            "end": round(float(sentence["end"]), 3),
            "text": sentence["text"],
            "query": query,
            "asset": choice["asset"],
            "score": choice["score"],
            "clip_in": 0.0,
            "clip_out": clip_len,
        })
    return plan


def filter_assets(assets: Sequence[dict[str, Any]], *, min_duration: float | None = None,
                  orientation: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    result = []
    for asset in assets:
        if kind and asset.get("kind") != kind:
            continue
        if min_duration is not None and asset.get("kind") == "video" and \
                float(asset.get("duration") or 0) < min_duration:
            continue
        width, height = asset.get("width"), asset.get("height")
        if orientation and width and height:
            if orientation == "vertical" and height <= width:
                continue
            if orientation == "horizontal" and width <= height:
                continue
            if orientation == "square" and abs(width - height) > 4:
                continue
        result.append(asset)
    return result


def write_manifest(path: str | Path, assets: Sequence[dict[str, Any]],
                   *, roots: Sequence[str] = ()) -> Path:
    return write_json(path, {
        "version": 1,
        "generated_by": "broll-finder-indexer",
        "roots": list(roots),
        "count": len(assets),
        "assets": list(assets),
    })


def read_manifest(path: str | Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if isinstance(data, list):
        return data
    if "assets" not in data:
        raise SkillError(f"Manifeste invalide : {path}")
    return data["assets"]


def ensure_manifest(roots: Sequence[str | Path] | None, manifest: str | Path | None,
                    *, recursive: bool = True, include_images: bool = True) -> list[dict[str, Any]]:
    if manifest:
        return read_manifest(manifest)
    if not roots:
        raise SkillError("Fournis --library DOSSIER (répétable) ou --manifest JSON.")
    return scan(roots, recursive=recursive, include_images=include_images)
