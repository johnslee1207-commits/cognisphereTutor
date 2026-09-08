"""Package an OpenMAIC standalone build as Tutor's bundled course runtime.

Usage:
    python scripts/package_openmaic_runtime.py --openmaic-root D:/Projects/_reference/OpenMAIC

The script expects `next build` to have produced `.next/standalone`. Pass
`--build` to run the OpenMAIC build first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

DEFAULT_OUTPUT = Path("cognispheretutor") / "vendor" / "openmaic-runtime"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    openmaic_root = args.openmaic_root.expanduser().resolve()
    output = args.output.expanduser().resolve()

    package_json = openmaic_root / "package.json"
    if not package_json.exists():
        raise SystemExit(f"OpenMAIC root is missing package.json: {openmaic_root}")

    if args.build:
        subprocess.run([_package_manager(openmaic_root), "run", "build"], cwd=openmaic_root, check=True)

    standalone = openmaic_root / ".next" / "standalone"
    if not standalone.exists():
        raise SystemExit(
            f"OpenMAIC standalone build not found: {standalone}. "
            "Run OpenMAIC `next build` first or pass --build."
        )

    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(standalone, output)

    static_src = openmaic_root / ".next" / "static"
    if static_src.exists():
        shutil.copytree(static_src, output / ".next" / "static", dirs_exist_ok=True)
    public_src = openmaic_root / "public"
    if public_src.exists():
        shutil.copytree(public_src, output / "public", dirs_exist_ok=True)

    manifest = {
        "version": 1,
        "name": "openmaic",
        "origin": args.origin.rstrip("/"),
        "health_path": "/api/health",
        "command": ["node", "server.js"],
        "cwd": ".",
        "export_routes": {
            "html": "/api/export/html",
            "pptx": "/api/export/pptx",
            "maic-zip": "/api/export/classroom",
        },
    }
    (output / "openmaic-runtime.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Packaged OpenMAIC runtime at {output}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openmaic-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--origin", default="http://127.0.0.1:33100")
    parser.add_argument("--build", action="store_true")
    return parser.parse_args(argv)


def _package_manager(root: Path) -> str:
    return "pnpm" if (root / "pnpm-lock.yaml").exists() else "npm"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
