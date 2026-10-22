#!/usr/bin/env python3
"""Studio vidéo VESK — importer et visualiser les vidéos du dépôt GitHub.

Usage : python3 studio/server.py  (PORT=… pour changer d port, défaut 8787)
API   : GET  /                    → interface
        GET  /api/videos          → liste des vidéos (arbre git = GitHub)
        GET  /api/status          → état de synchronisation de la branche
        POST /api/sync            → git fetch + info
        GET  /api/thumb?path=…    → vignette JPEG (générée à la volée)
        GET  /files/<chemin>      → flux vidéo avec support Range (206)
        POST /api/import?name=…   → corps brut = fichier → imports/ + push GitHub
"""
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STUDIO = Path(__file__).resolve().parent
ROOT = STUDIO.parent
THUMBS = STUDIO / ".cache" / "thumbs"
IMPORTS = ROOT / "imports"
BRANCH = "arena/c7b98586-essaie"
REPO = "gnansounoujerode3-hue/essaie"
GH_BLOB = f"https://github.com/{REPO}/blob/{BRANCH}"
GH_RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
MAX_UPLOAD = 95 * 1024 * 1024  # limite GitHub = 100 Mo par fichier
DUR_CACHE = {}
GIT_LOCK = threading.Lock()


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def git(*args, timeout=300):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=timeout)


def parse_duration(path: Path):
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                          capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        return None
    h, mn, sec = m.groups()
    return round(int(h) * 3600 + int(mn) * 60 + float(sec), 2)


def ensure_thumb(rel: str):
    src = ROOT / rel
    THUMBS.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]
    out = THUMBS / f"{key}.jpg"
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    for ss in ("1", "0.1"):
        subprocess.run(
            [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
             "-ss", ss, "-i", str(src), "-frames:v", "1",
             "-vf", "scale=360:-2", "-q:v", "5", str(out)],
            capture_output=True, timeout=60)
        if out.exists() and out.stat().st_size > 0:
            return out
    return None


def tracked_videos():
    """Arbre de HEAD = état du dépôt GitHub (après push)."""
    out = {}
    proc = git("-c", "core.quotepath=false", "ls-tree", "-r", "-l", "HEAD")
    if proc.returncode != 0:
        return out
    for line in proc.stdout.splitlines():
        meta, sep, name = line.partition("\t")
        parts = meta.split()
        if sep and len(parts) >= 4 and parts[1] == "blob":
            if Path(name).suffix.lower() in VIDEO_EXT:
                out[name] = int(parts[3])
    return out


def list_videos():
    tracked = tracked_videos()
    names = dict(tracked)
    for p in ROOT.rglob("*"):
        if (p.is_file() and p.suffix.lower() in VIDEO_EXT
                and not any(seg.startswith(".") for seg in p.relative_to(ROOT).parts)):
            names.setdefault(str(p.relative_to(ROOT)), 0)
    items = []
    for rel in sorted(names):
        path = ROOT / rel
        if not path.is_file():
            continue
        st = path.stat()
        if st.st_mtime != DUR_CACHE.get(rel, {}).get("mtime"):
            DUR_CACHE[rel] = {"mtime": st.st_mtime, "dur": parse_duration(path)}
        enc = urllib.parse.quote(rel, safe="/")
        items.append({
            "name": path.name,
            "path": rel,
            "size": st.st_size,
            "duration": DUR_CACHE[rel]["dur"],
            "synced": rel in tracked,
            "thumb": f"/api/thumb?path={urllib.parse.quote(rel)}",
            "file": f"/files/{enc}",
            "github": f"{GH_BLOB}/{enc}",
            "raw": f"{GH_RAW}/{enc}",
        })
    return items


def branch_status():
    head = git("rev-parse", "--short", "HEAD").stdout.strip()
    proc = git("rev-parse", "--short", f"origin/{BRANCH}")
    origin = proc.stdout.strip() if proc.returncode == 0 else None
    dirty = bool(git("status", "--porcelain").stdout.strip())
    return {"branch": BRANCH, "head": head, "origin": origin,
            "in_sync": origin is not None and head == origin, "dirty": dirty}


def safe_path(rel: str) -> Path:
    path = (ROOT / urllib.parse.unquote(rel)).resolve()
    if not str(path).startswith(str(ROOT) + os.sep):
        raise ValueError("hors dépôt")
    return path


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "StudioVESK/1.0"

    # --- helpers -------------------------------------------------------
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, inline=True):
        if not path.is_file():
            return self._json({"error": "introuvable"}, 404)
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        status = 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m and (m.group(1) or m.group(2)):
                start = int(m.group(1) or 0)
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
                else:
                    end = size - 1
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if not inline:
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"{path.name.encode('ascii', 'ignore').decode()}\"")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(1 << 20, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    # --- routes --------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        route, qs = parsed.path, urllib.parse.parse_qs(parsed.query)
        try:
            if route in ("/", "/index.html"):
                return self._file(STUDIO / "index.html")
            if route == "/api/videos":
                return self._json({"videos": list_videos()})
            if route == "/api/status":
                return self._json(branch_status())
            if route == "/api/thumb":
                return self._file(ensure_thumb(qs.get("path", [""])[0]))
            if route.startswith("/files/"):
                return self._file(safe_path(route[len("/files/"):]))
            return self._json({"error": "route inconnue"}, 404)
        except ValueError as exc:
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001 — journalisé en réponse
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        route, qs = parsed.path, urllib.parse.parse_qs(parsed.query)
        try:
            if route == "/api/sync":
                fetch = git("fetch", "origin", BRANCH, timeout=180)
                st = branch_status()
                st["fetched"] = fetch.returncode == 0
                st["fetch_error"] = fetch.stderr.strip()[-300:] if fetch.returncode else None
                return self._json(st)
            if route == "/api/import":
                return self._import(qs.get("name", [""])[0])
            return self._json({"error": "route inconnue"}, 404)
        except Exception as exc:  # noqa: BLE001
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def _import(self, raw_name: str):
        name = os.path.basename(urllib.parse.unquote(raw_name)).strip()
        if not name or Path(name).suffix.lower() not in VIDEO_EXT:
            return self._json({"error": "extension vidéo attendue"}, 400)
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._json({"error": "corps vide"}, 400)
        if length > MAX_UPLOAD:
            return self._json(
                {"error": "fichier trop volumineux (limite GitHub : 100 Mo)"}, 413)
        IMPORTS.mkdir(exist_ok=True)
        tmp = IMPORTS / f".{name}.part"
        dest = IMPORTS / name
        remaining = length
        with open(tmp, "wb") as fh:
            while remaining > 0:
                chunk = self.rfile.read(min(1 << 20, remaining))
                if not chunk:
                    break
                fh.write(chunk)
                remaining -= len(chunk)
        if remaining:
            tmp.unlink(missing_ok=True)
            return self._json({"error": "transmission interrompue"}, 400)
        tmp.replace(dest)
        rel = str(dest.relative_to(ROOT))
        with GIT_LOCK:
            git("add", "--", rel)
            staged = git("diff", "--cached", "--quiet", "--", rel)
            pushed = False
            commit_msg = ""
            if staged.returncode != 0:  # quelque chose a changé
                commit = git("commit", "-m", f"studio: import « {name} »", "--", rel)
                if commit.returncode != 0:
                    dest.unlink(missing_ok=True)
                    return self._json({"error": commit.stderr.strip()[-300:]}, 500)
                push = git("push", "origin", BRANCH, timeout=600)
                if push.returncode != 0:
                    return self._json({
                        "error": "importé localement, push échoué : "
                                 + push.stderr.strip()[-300:]}, 502)
                pushed = True
                commit_msg = git("rev-parse", "--short", "HEAD").stdout.strip()
            else:
                git("reset", "-q", "HEAD", "--", rel)
                pushed = True  # déjà identique à HEAD
        return self._json({"ok": True, "path": rel, "pushed": pushed,
                           "commit": commit_msg, "size": dest.stat().st_size})

    def log_message(self, fmt, *args):
        pass  # silence


def main():
    port = int(os.environ.get("PORT") or 8787)
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Studio VESK → http://0.0.0.0:{port}  (branche {BRANCH})")
    server.serve_forever()


if __name__ == "__main__":
    main()
