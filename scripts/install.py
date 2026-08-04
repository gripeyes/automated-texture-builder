#!/usr/bin/env python3
"""Install the Houdini package and Painter preset for the current user."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent.parent
PRESET_NAME = "Automated Texture Builder - Rec2020 TX Pipeline.spexp"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--houdini-version", default="22.0")
    parser.add_argument("--skip-painter", action="store_true")
    args = parser.parse_args()

    package_dir = (
        Path.home() / "Library" / "Preferences" / "houdini" /
        args.houdini_version / "packages"
    )
    package_dir.mkdir(parents=True, exist_ok=True)
    package_path = package_dir / "automated_texture_builder.json"
    package = {
        "enable": True,
        "env": [
            {"AUTOMATED_TEXTURE_BUILDER_ROOT": str(ROOT)},
            {"PYTHONPATH": "$AUTOMATED_TEXTURE_BUILDER_ROOT/python"},
            {"HOUDINI_OTLSCAN_PATH": "$AUTOMATED_TEXTURE_BUILDER_ROOT/otls;&"},
        ],
    }
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    print(f"Installed Houdini package: {package_path}")

    if not args.skip_painter:
        painter_dir = (
            Path.home() / "Documents" / "Adobe" / "Adobe Substance 3D Painter" /
            "assets" / "export-presets"
        )
        painter_dir.mkdir(parents=True, exist_ok=True)
        painter_path = painter_dir / PRESET_NAME
        shutil.copy2(ROOT / "presets" / PRESET_NAME, painter_path)
        print(f"Installed Painter preset: {painter_path}")

    print("Restart Houdini 22 and Painter so they rescan the installed assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
