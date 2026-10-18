from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from shortsforge.server import StudioHandler, StudioState


class StudioHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        out = self.root / "output"
        out.mkdir()
        (out / "sample.mp4").write_bytes(b"0123456789abcdef")
        StudioHandler.state = StudioState(self.root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), StudioHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, method: str, path: str, *, body: bytes = b"", headers: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        status = response.status
        response_headers = dict(response.getheaders())
        conn.close()
        return status, response_headers, data

    def test_health_route(self) -> None:
        status, _, body = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_video_byte_range(self) -> None:
        status, headers, body = self.request("GET", "/media/sample.mp4", headers={"Range": "bytes=3-6"})
        self.assertEqual(status, 206)
        self.assertEqual(body, b"3456")
        self.assertEqual(headers["Content-Range"], "bytes 3-6/16")

    def test_render_rejects_path_traversal(self) -> None:
        status, _, body = self.request(
            "POST", "/api/render", body=json.dumps({"spec": "../../etc/passwd"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)
        self.assertIn("interdit", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()
