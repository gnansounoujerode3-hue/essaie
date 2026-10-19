#!/usr/bin/env python3
"""Vérifie la syntaxe JavaScript des scripts ExtendScript générés.

ExtendScript n'est pas du JavaScript Node : on retire les directives
`#target`/`#targetengine`/`#include` avant de demander à Node de valider la syntaxe.

Usage :
  python3 tests/check_jsx.py            # exemple du dépôt
  python3 tests/check_jsx.py fichier.jsx [autres.jsx]
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from vesk.nle_aftereffects import build_ae_jsx  # noqa: E402
from vesk.nle_premiere import (jsx_export, jsx_import_plan,  # noqa: E402
                               jsx_markers, normalize_plan)

DIRECTIVE = re.compile(r"^\s*#(?:target|targetengine|include)\b.*$", re.MULTILINE)


def strip_directives(source: str) -> str:
    return DIRECTIVE.sub("", source)


def check_with_node(source: str, label: str) -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return True, f"{label}: node absent, contrôle ignoré"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(strip_directives(source))
        temp = Path(handle.name)
    try:
        result = subprocess.run([node, "--check", str(temp)],
                                capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, f"{label}: syntaxe OK"
        return False, f"{label}: {result.stderr.strip().splitlines()[0] if result.stderr else 'échec'}"
    finally:
        temp.unlink(missing_ok=True)


def generate_samples() -> dict[str, str]:
    plan = normalize_plan(json.loads((ROOT / "examples" / "edit-example.json")
                                     .read_text(encoding="utf-8")))
    return {
        "premiere/import.jsx": jsx_import_plan(plan),
        "premiere/markers.jsx": jsx_markers(plan["markers"], sequence_name=plan["name"]),
        "premiere/export.jsx": jsx_export(plan["name"], "export.mp4"),
        "after-effects/assembly.jsx": build_ae_jsx(plan),
    }


def main(argv: list[str]) -> int:
    failures = 0
    if len(argv) > 1:
        sources = {path: Path(path).read_text(encoding="utf-8") for path in argv[1:]}
    else:
        sources = generate_samples()
        out_dir = Path(tempfile.mkdtemp(prefix="vesk-jsx-"))
        for name, content in sources.items():
            (out_dir / name.replace("/", "-")).write_text(content, encoding="utf-8")
        print(f"▸ Échantillons écrits dans {out_dir}")
    for name, source in sources.items():
        ok, message = check_with_node(source, name)
        print(("  ✓ " if ok else "  ✗ ") + message)
        failures += 0 if ok else 1
    if failures:
        print(f"\n{failures} script(s) invalide(s)")
        return 1
    print("\n✅ Tous les scripts ExtendScript sont syntaxiquement valides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
