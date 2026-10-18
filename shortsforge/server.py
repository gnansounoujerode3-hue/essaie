"""Studio web : aperçu des rendus, bibliothèque de skills, rendu à la demande.

Lancement :  ``sf studio --port 8080``
Le serveur écoute sur 0.0.0.0 pour être accessible depuis le navigateur.
"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
import traceback
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

from . import skills as skills_mod
from .qa import analyze
from .spec import ShortSpec

STUDIO_DIR = Path(__file__).resolve().parent / "studio"

MIME = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".mp3": "audio/mpeg",
}


class StudioState:
    """État partagé (rendus en cours, cache QA)."""

    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.Lock()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.qa_cache: Dict[str, Dict[str, Any]] = {}
        self.qa_cache_signatures: Dict[str, tuple] = {}
        self.media_cache: Dict[str, Dict[str, Any]] = {}

    # -- rendus -------------------------------------------------------- #
    def output_dir(self) -> Path:
        return self.root / "output"

    def renders(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        outdir = self.output_dir()
        if not outdir.exists():
            return out
        for path in sorted(outdir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
            key = path.name
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime)
            with self.lock:
                qa = self.qa_cache.get(key) if self.qa_cache_signatures.get(key) == signature else None
                cached = self.media_cache.get(key)
            if not cached or cached.get("signature") != signature:
                try:
                    from .ffmpeg import probe

                    info = probe(path)
                    cached = {
                        "signature": signature,
                        "duration": info.duration,
                        "width": info.width,
                        "height": info.height,
                    }
                except Exception:
                    cached = {"signature": signature}
                with self.lock:
                    self.media_cache[key] = cached
            if qa is None and stat.st_size > 0 and time.time() - stat.st_mtime > 1.0 and not self._is_rendering(path.stem):
                spec = self._find_spec(path.stem)
                if spec is not None:
                    try:
                        report = analyze(spec, path, root=self.root)
                        qa = report.to_dict()
                        with self.lock:
                            self.qa_cache[key] = qa
                            self.qa_cache_signatures[key] = signature
                    except Exception:
                        qa = None
            item: Dict[str, Any] = {
                "name": path.name,
                "slug": path.stem,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "url": f"/media/{path.name}",
                "qa": qa,
                "duration": cached.get("duration"),
                "width": cached.get("width"),
                "height": cached.get("height"),
            }
            # Miniature au milieu de la vidéo (créée une seule fois).
            thumb = outdir / ".thumbs" / f"{path.stem}.jpg"
            if not thumb.exists() and cached.get("duration"):
                try:
                    from .ffmpeg import ffmpeg_bin
                    import subprocess

                    thumb.parent.mkdir(parents=True, exist_ok=True)
                    at = max(0.05, min(cached["duration"] * 0.35, cached["duration"] - 0.05))
                    subprocess.run(
                        [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{at:.3f}",
                         "-i", str(path), "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "3", str(thumb)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                    )
                except Exception:
                    pass
            if thumb.exists():
                item["thumb"] = f"/media/.thumbs/{path.stem}.jpg"
            out.append(item)
        return out

    def specs(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for folder in ("examples", "assets/specs"):
            base = self.root / folder
            if not base.exists():
                continue
            for path in sorted(base.glob("*.y*ml")) + sorted(base.glob("*.json")):
                out.append({"name": path.name, "folder": folder, "path": f"{folder}/{path.name}"})
        return out

    def _find_spec(self, slug: str) -> Optional[ShortSpec]:
        for folder in ("examples", "assets/specs"):
            base = self.root / folder
            if not base.exists():
                continue
            for path in sorted(base.glob("*.y*ml")) + sorted(base.glob("*.json")):
                try:
                    spec = ShortSpec.load(path)
                    if spec.slug == slug:
                        return spec
                except Exception:
                    continue
        return None

    def _is_rendering(self, slug: str) -> bool:
        with self.lock:
            jobs = list(self.jobs.values())
        for job in jobs:
            if job.get("status") != "running":
                continue
            try:
                path = (self.root / job.get("spec", "")).resolve()
                if self.root.resolve() not in path.parents or not path.is_file():
                    continue
                if ShortSpec.load(path).slug == slug:
                    return True
            except Exception:
                continue
        return False

    def start_render(self, spec_path: str) -> Dict[str, Any]:
        job_id = f"job_{int(time.time() * 1000)}"
        with self.lock:
            self.jobs[job_id] = {"id": job_id, "status": "running", "spec": spec_path, "log": [], "started": time.time()}
        thread = threading.Thread(target=self._run_render, args=(job_id, spec_path), daemon=True)
        thread.start()
        print(f"[Studio] {job_id} — rendu démarré : {spec_path}", flush=True)
        return self.jobs[job_id]

    def _run_render(self, job_id: str, spec_path: str) -> None:
        from .renderer import render_spec

        try:
            path = (self.root / spec_path).resolve()
            if not path.exists() or self.root.resolve() not in path.parents:
                raise FileNotFoundError(spec_path)
            spec = ShortSpec.load(path)
            result = render_spec(spec, root=self.root, verbose=False)
            report = analyze(spec, result.output, root=self.root)
            stat = result.output.stat()
            with self.lock:
                self.qa_cache[result.output.name] = report.to_dict()
                self.qa_cache_signatures[result.output.name] = (stat.st_size, stat.st_mtime)
                self.media_cache[result.output.name] = {
                    "signature": (stat.st_size, stat.st_mtime),
                    "duration": result.duration,
                    "width": result.width,
                    "height": result.height,
                }
                self.jobs[job_id] = {
                    "id": job_id,
                    "status": "done",
                    "spec": spec_path,
                    "output": result.output.name,
                    "score": report.score,
                    "grade": report.grade,
                    "warnings": result.warnings,
                    "log": [f"✔ {result.output.name}", f"Score {report.score}/100 ({report.grade})"],
                }
            print(f"[Studio] {job_id} — terminé : {result.output.name}, QA {report.score}/100 ({report.grade})", flush=True)
        except Exception as exc:  # pragma: no cover
            with self.lock:
                self.jobs[job_id] = {
                    "id": job_id,
                    "status": "error",
                    "spec": spec_path,
                    "log": traceback.format_exc(limit=4).splitlines()[-6:],
                    "error": str(exc),
                }
            print(f"[Studio] {job_id} — échec : {exc}", flush=True)


class StudioHandler(BaseHTTPRequestHandler):
    state: StudioState = None  # type: ignore
    server_version = "ShortsForge/1.0"

    def log_message(self, fmt: str, *args) -> None:  # pragma: no cover
        pass

    # -- utilitaires --------------------------------------------------- #
    def _jobs_snapshot(self) -> List[Dict[str, Any]]:
        with self.state.lock:
            return [dict(job) for job in self.state.jobs.values()]

    def _send(self, code: int, body: bytes, content_type: str = "application/json", extra: Optional[Dict[str, str]] = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = MIME.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        size = path.stat().st_size
        range_header = self.headers.get("Range", "")
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip()) if range_header else None
        if match:
            first, last = match.groups()
            if first:
                start = int(first)
                end = int(last) if last else size - 1
            elif last:
                length = int(last)
                start, end = max(0, size - length), size - 1
            else:
                start, end = 0, size - 1
            if start >= size or end < start:
                self._send(416, b"", ctype, {"Content-Range": f"bytes */{size}"})
                return
            end = min(end, size - 1)
            with path.open("rb") as f:
                f.seek(start)
                data = f.read(end - start + 1)
            self._send(206, data, ctype, {"Content-Range": f"bytes {start}-{end}/{size}"})
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            with path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    # -- routes --------------------------------------------------------- #
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if route in ("/", "/index.html"):
            return self._file(STUDIO_DIR / "index.html")
        if route == "/style.css":
            return self._file(STUDIO_DIR / "style.css")
        if route == "/app.js":
            return self._file(STUDIO_DIR / "app.js")
        if route == "/api/state":
            return self._json(
                {
                    "skills": [s.to_dict() for s in skills_mod.load_all()],
                    "renders": self.state.renders(),
                    "specs": self.state.specs(),
                    "jobs": self._jobs_snapshot(),
                }
            )
        if route.startswith("/api/skill/"):
            skill_id = route.split("/api/skill/", 1)[1]
            try:
                skill = skills_mod.get(skill_id)
            except KeyError:
                return self._json({"error": "skill inconnu"}, 404)
            return self._json({**skill.to_dict(), "body": skill.body})
        if route.startswith("/api/spec/"):
            spec_path = route.split("/api/spec/", 1)[1]
            path = (self.state.root / spec_path).resolve()
            if self.state.root.resolve() not in path.parents:
                return self._json({"error": "chemin interdit"}, 403)
            if not path.is_file():
                return self._json({"error": "spec introuvable"}, 404)
            try:
                spec = ShortSpec.load(path)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
            return self._json(spec.to_dict())
        if route.startswith("/media/"):
            rel = route[len("/media/") :]
            path = (self.state.output_dir() / rel).resolve()
            if self.state.output_dir().resolve() not in path.parents:
                return self._send(403, b"forbidden", "text/plain")
            return self._file(path)
        if route == "/healthz":
            return self._json({"ok": True})
        return self._send(404, b"not found", "text/plain")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}
        if route == "/api/render":
            spec_path = payload.get("spec") or ""
            if not spec_path:
                return self._json({"error": "spec manquant"}, 400)
            path = (self.state.root / spec_path).resolve()
            if self.state.root.resolve() not in path.parents:
                return self._json({"error": "chemin interdit"}, 403)
            if not path.is_file():
                return self._json({"error": "spec introuvable"}, 404)
            job = self.state.start_render(spec_path)
            return self._json(job, 202)
        if route == "/api/qa":
            spec_path = payload.get("spec") or ""
            path = (self.state.root / spec_path).resolve()
            if self.state.root.resolve() not in path.parents:
                return self._json({"error": "chemin interdit"}, 403)
            if not path.is_file():
                return self._json({"error": "spec introuvable"}, 404)
            try:
                spec = ShortSpec.load(path)
                output = self.state.output_dir() / f"{spec.slug}.mp4"
                report = analyze(spec, output if output.exists() else None, root=self.state.root)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
            key = f"{spec.slug}.mp4"
            with self.state.lock:
                self.state.qa_cache[key] = report.to_dict()
                if output.exists():
                    stat = output.stat()
                    self.state.qa_cache_signatures[key] = (stat.st_size, stat.st_mtime)
            return self._json(report.to_dict())
        return self._send(404, b"not found", "text/plain")


def serve(host: str = "0.0.0.0", port: int = 8080, root: Optional[Path] = None) -> None:
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    StudioHandler.state = StudioState(root)
    httpd = ThreadingHTTPServer((host, port), StudioHandler)
    print(f"ShortsForge Studio → http://{host}:{port}  (racine : {root})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du studio.")
    finally:
        httpd.server_close()
