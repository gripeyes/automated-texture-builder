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
    parser.add_argument(
        "--houdini-version",
        action="append",
        dest="houdini_versions",
        help=(
            "Houdini preference version to install (repeat for more than one). "
            "Defaults to 20.5 and 22.0."
        ),
    )
    parser.add_argument("--skip-painter", action="store_true")
    args = parser.parse_args()

    package = {
        "enable": True,
        "env": [
            {"AUTOMATED_TEXTURE_BUILDER_ROOT": str(ROOT)},
            {"PYTHONPATH": "$AUTOMATED_TEXTURE_BUILDER_ROOT/python"},
            {"HOUDINI_OTLSCAN_PATH": "$AUTOMATED_TEXTURE_BUILDER_ROOT/otls;&"},
        ],
    }
    houdini_versions = args.houdini_versions or ["20.5", "22.0"]
    for houdini_version in dict.fromkeys(houdini_versions):
        package_dir = (
            Path.home() / "Library" / "Preferences" / "houdini" /
            houdini_version / "packages"
        )
        package_dir.mkdir(parents=True, exist_ok=True)
        package_path = package_dir / "automated_texture_builder.json"
        package_path.write_text(
            json.dumps(package, indent=2) + "\n",
            encoding="utf-8",
        )
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

    print("Restart each installed Houdini version and Painter to rescan the assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
