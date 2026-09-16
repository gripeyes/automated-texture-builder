#!/usr/bin/env python3
"""Validate Automated Texture Builder's native MoonRay graph in Houdini."""

from __future__ import annotations

from pathlib import Path
import sys

import hou


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from automated_texture_builder.houdini import materials  # noqa: E402


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _validate_builder(builder: hou.Node, displacement_kind: str) -> None:
    _require(builder.shaderLanguageName() == "VEX", "builder is not a VEX subnet")
    context = builder.parm("shader_rendercontextname")
    _require(context is not None and context.eval() == "moonray", "missing moonray render context")
    _require(builder.outputNames() == ("surface", "displacement"), "incorrect builder outputs")
    _require(
        tuple(str(kind) for kind in builder.outputDataTypes()) == ("surface", "displacement"),
        "incorrect builder output datatypes",
    )

    outputs = [node for node in builder.children() if node.type().name() == "suboutput"]
    connectors = [node for node in builder.children() if node.type().name() == "subnetconnector"]
    _require(len(outputs) == 1, "builder must contain exactly one suboutput")
    _require(not connectors, "builder contains obsolete generated subnetconnector outputs")

    output = outputs[0]
    surface = builder.node("dwa_base")
    displacement = builder.node(
        "vector_displacement" if displacement_kind == "vector" else "normal_displacement"
    )
    _require(surface is not None and output.input(0) == surface, "surface output is not connected")
    _require(displacement is not None and output.input(1) == displacement, "displacement output is not connected")

    image = builder.node("basecolor")
    _require(image is not None, "base-color ImageMap is missing")
    _require(image.outputNames() == ("map",), "ImageMap does not expose its map output")
    _require(tuple(str(kind) for kind in image.outputDataTypes()) == ("vector",), "ImageMap is not vector")
    albedo_index = surface.inputNames().index("albedo")
    _require(surface.input(albedo_index) == image, "ImageMap is not connected to DwaBaseMaterial.albedo")

    roughness = builder.node("base_diffuse_roughness_image")
    roughness_index = surface.inputNames().index("diffuse_roughness")
    _require(roughness is not None and surface.input(roughness_index) == roughness, "scalar map is disconnected")

    if displacement_kind == "height":
        height = builder.node("height_red")
        _require(height is not None, "height extraction node is missing")
        height_index = displacement.inputNames().index("height")
        _require(displacement.input(height_index) == height, "height displacement is disconnected")
        _require(displacement.parm("height_multiplier").eval() == 0.01, "height scale was not authored")
    elif displacement_kind == "vector":
        vector_image = builder.node("vector_displacement_image")
        vector_index = displacement.inputNames().index("vector")
        _require(vector_image is not None and displacement.input(vector_index) == vector_image, "vector displacement is disconnected")
        _require(displacement.parm("factor").eval() == 0.01, "vector displacement scale was not authored")
        _require(builder.node("normal_displacement") is None, "unused default displacement remains")
    else:
        _require(displacement.parm("height_multiplier").eval() == 0.0, "default displacement is active")

    for node in (builder, output, surface, displacement, image, roughness):
        _require(not node.errors(), f"{node.path()} reports errors: {node.errors()}")
        _require(not node.warnings(), f"{node.path()} reports warnings: {node.warnings()}")


def main() -> None:
    stage = hou.node("/stage")
    library = stage.createNode("materiallibrary", "atb_moonray_validation")
    data = {
        "texture_sets": [
            {
                "name": "with_height",
                "maps": {
                    "base_color": {"path": "/tmp/base.tx", "lookup_space": "Raw"},
                    "base_diffuse_roughness": {"path": "/tmp/rough.tx", "lookup_space": "Raw"},
                    "height": {"path": "/tmp/height.tx", "lookup_space": "Raw"},
                },
            },
            {
                "name": "without_height",
                "maps": {
                    "base_color": {"path": "/tmp/base.tx", "lookup_space": "Raw"},
                    "base_diffuse_roughness": {"path": "/tmp/rough.tx", "lookup_space": "Raw"},
                },
            },
            {
                "name": "with_vector_displacement",
                "maps": {
                    "base_color": {"path": "/tmp/base.tx", "lookup_space": "Raw"},
                    "base_diffuse_roughness": {"path": "/tmp/rough.tx", "lookup_space": "Raw"},
                    "vector_displacement": {"path": "/tmp/vector.tx", "lookup_space": "Raw"},
                },
            },
        ]
    }
    materials._build_moonray(library, data, "repeat", 0.01, 0.0, "displacement")
    _validate_builder(library.node("with_height"), displacement_kind="height")
    _validate_builder(library.node("without_height"), displacement_kind="none")
    _validate_builder(library.node("with_vector_displacement"), displacement_kind="vector")
    print("Validated canonical MoonRay material authoring and displacement variants.")


if __name__ == "__main__":
    main()
