from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "package_openmaic_runtime.py"
SPEC = importlib.util.spec_from_file_location("package_openmaic_runtime", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
package_openmaic_runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_openmaic_runtime)


def test_package_openmaic_runtime_copies_standalone_and_manifest(tmp_path: Path) -> None:
    openmaic = tmp_path / "OpenMAIC"
    standalone = openmaic / ".next" / "standalone"
    static = openmaic / ".next" / "static"
    public = openmaic / "public"
    output = tmp_path / "runtime"
    standalone.mkdir(parents=True)
    static.mkdir(parents=True)
    public.mkdir(parents=True)
    (openmaic / "package.json").write_text('{"name":"openmaic"}', encoding="utf-8")
    (standalone / "server.js").write_text("console.log('openmaic')", encoding="utf-8")
    (static / "chunk.js").write_text("chunk", encoding="utf-8")
    (public / "logo.svg").write_text("<svg />", encoding="utf-8")

    result = package_openmaic_runtime.main(
        [
            "--openmaic-root",
            str(openmaic),
            "--output",
            str(output),
            "--origin",
            "http://127.0.0.1:33155",
        ]
    )

    manifest = json.loads((output / "openmaic-runtime.json").read_text(encoding="utf-8"))
    assert result == 0
    assert (output / "server.js").exists()
    assert (output / ".next" / "static" / "chunk.js").exists()
    assert (output / "public" / "logo.svg").exists()
    assert manifest["origin"] == "http://127.0.0.1:33155"
    assert manifest["command"] == ["node", "server.js"]
    assert manifest["export_routes"] == {
        "html": "/api/export/html",
        "pptx": "/api/export/pptx",
        "maic-zip": "/api/export/classroom",
    }
