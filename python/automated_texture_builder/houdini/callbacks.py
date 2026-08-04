from __future__ import annotations

from pathlib import Path
import json
import traceback

import hou

from automated_texture_builder.conversion import (
    COLOR_CHANNELS, classify, convert, delete_original_sources,
    delete_sources_for_existing_tx, load_ocio, manifest_existing_tx,
    manifest_source_images, resolve_existing_tx_root, resolve_ocio,
    scene_linear_space,
)
from automated_texture_builder.discovery import scan
from .materials import auto_assign, build_materials


def _parm(node: hou.Node, name: str, default=""):
    parm = node.parm(name)
    return parm.eval() if parm is not None else default


def _menu(node: hou.Node, name: str) -> str:
    parm = node.parm(name)
    if parm is None:
        raise RuntimeError(f"Missing menu parameter: {name}")
    return parm.evalAsString()


def refresh_scene_linear(node: hou.Node, show_errors: bool = False) -> str:
    """Refresh the read-only OCIO role display without building materials."""
    try:
        explicit = None if node.evalParm("use_houdini_ocio") else node.evalParm("ocio_config")
        ocio_path = resolve_ocio(explicit)
        value = scene_linear_space(load_ocio(ocio_path))
        node.parm("scene_linear_space").set(value)
        node.parm("active_ocio_config").set(str(ocio_path))
        refresh_color_rules(node)
        return value
    except Exception as exc:
        node.parm("scene_linear_space").set("Unavailable")
        node.parm("active_ocio_config").set(str(exc))
        if show_errors:
            _message(str(exc), True)
        return ""


def _set_if_present(node: hou.Node, name: str, value: str) -> None:
    parm = node.parm(name)
    if parm is not None:
        parm.set(value)


def _display_space_name(config, value: str) -> str:
    """Display the config-family spelling while classification remains rule-driven."""
    colorspace = config.getColorSpace(value)
    if colorspace is None:
        return value
    if scene_linear_space(config).casefold() == "acescg":
        aliases = list(colorspace.getAliases())
        preferred = next((alias for alias in aliases if alias.startswith("sRGB Encoded")), None)
        if preferred:
            return preferred
    return colorspace.getName()


def _tx_rule_status(config) -> str:
    tx_space = classify(config, Path("/tmp/AutomatedTextureBuilder_ColorTexture.tx"))
    if tx_space.casefold() == "raw":
        return "Correct: OCIO config maps .tx files to Raw — no second conversion."
    return (
        f"WARNING: OCIO maps .tx files to {tx_space}. Set the .tx file rule to Raw "
        "to avoid double conversion."
    )


def refresh_color_rules(node: hou.Node) -> None:
    """Summarize real OCIO classifications for source textures by file type."""
    fields = ("rule_exr", "rule_tiff", "rule_web", "rule_data", "rule_target", "rule_tx")
    workflow = _menu(node, "texture_workflow")
    try:
        explicit = None if node.evalParm("use_houdini_ocio") else node.evalParm("ocio_config")
        config = load_ocio(resolve_ocio(explicit))
        tx_rule_status = _tx_rule_status(config)
    except Exception as exc:
        for name in fields:
            _set_if_present(node, name, f"Unavailable: {exc}")
        return
    if workflow == "existing_tx":
        for name in fields[:3]:
            _set_if_present(node, name, "Not applicable — using existing TX files")
        _set_if_present(node, "rule_data", "Existing TX data maps remain Raw — no transform")
        _set_if_present(node, "rule_target", "No conversion — using existing TX files")
        _set_if_present(node, "rule_tx", tx_rule_status)
        return
    source_text = node.evalParm("texture_folder").strip()
    source = Path(source_text).expanduser() if source_text else None
    if source is None or not source.is_dir():
        for name in fields[:3]:
            _set_if_present(node, name, "Select a Source Texture Folder")
        _set_if_present(node, "rule_data", "Raw → Raw — no OCIO transform")
        _set_if_present(
            node, "rule_target",
            "No TX conversion" if workflow == "source_direct" else "OCIO scene-linear",
        )
        _set_if_present(
            node, "rule_tx",
            tx_rule_status,
        )
        return
    try:
        destination = scene_linear_space(config)
        texture_sets = scan(source, (source / "tx").resolve())
        groups = {
            "rule_exr": {".exr"},
            "rule_tiff": {".tif", ".tiff"},
            "rule_web": {".png", ".jpg", ".jpeg"},
        }
        textures = [
            texture
            for texture_set in texture_sets.values()
            for channel_textures in texture_set.maps.values()
            for texture in channel_textures
        ]
        for field, extensions in groups.items():
            spaces = sorted({
                _display_space_name(config, classify(config, texture.source))
                for texture in textures
                if texture.channel in COLOR_CHANNELS and texture.source.suffix.lower() in extensions
            })
            if spaces:
                text = f"Read as {', '.join(spaces)} (detected source maps)"
            else:
                fallback_spaces = sorted({
                    _display_space_name(
                        config,
                        classify(config, Path("/tmp") / f"AutomatedTextureBuilder_BaseColor{extension}"),
                    )
                    for extension in extensions
                })
                text = (
                    f"Read as {', '.join(fallback_spaces)} "
                    "(OCIO extension rule; no matching maps found)"
                )
            _set_if_present(node, field, text)
        data_count = sum(texture.channel not in COLOR_CHANNELS for texture in textures)
        _set_if_present(
            node,
            "rule_data",
            f"Raw → Raw — no OCIO transform ({data_count} file(s) found)",
        )
        if workflow == "source_direct":
            _set_if_present(node, "rule_target", "No TX conversion — source images used directly")
            _set_if_present(node, "rule_tx", tx_rule_status)
        else:
            _set_if_present(node, "rule_target", f"All color TX pixels → {destination}")
            _set_if_present(node, "rule_tx", tx_rule_status)
    except Exception as exc:
        for name in fields:
            _set_if_present(node, name, f"Unavailable: {exc}")


def refresh_maketx_behavior(node: hou.Node) -> str:
    workflow = _menu(node, "texture_workflow")
    force_enabled = bool(node.evalParm("force_rebuild"))
    if workflow == "source_direct":
        text = "Source images direct: no TX files are generated."
    elif workflow == "existing_tx":
        text = "Existing TX: maketx will not run or regenerate files."
    elif force_enabled:
        text = "Regenerate all TX: every source texture replaces its TX output."
    else:
        text = "Incremental TX: missing, outdated, or incorrectly stored TX files are generated."
    parm = node.parm("maketx_behavior")
    if parm is not None:
        parm.set(text)
    refresh_color_rules(node)
    return text


def _update_conversion_summary(node: hou.Node, manifest: Path, workflow: str) -> str:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    textures = data.get("textures", [])
    color_count = sum(item.get("channel") in COLOR_CHANNELS for item in textures)
    data_count = len(textures) - color_count
    scene_linear = data.get("color_output_space", "the OCIO scene-linear space")
    if workflow == "generate_tx":
        failed = [item for item in textures if item.get("status") == "failed"]
        if failed:
            summary = f"Failed: {len(failed)} of {len(textures)} texture files did not convert."
        else:
            summary = (
                f"Success: {len(textures)} files — {color_count} color → {scene_linear}; "
                f"{data_count} data → Raw."
            )
    elif workflow == "existing_tx":
        summary = (
            f"Success: {len(textures)} existing TX files; maketx not run — "
            f"{color_count} color, {data_count} Raw data."
        )
    else:
        summary = (
            f"Success: {len(textures)} source files used directly — "
            f"{color_count} color, {data_count} Raw data; maketx not run."
        )
    node.parm("conversion_summary").set(summary)
    return summary


def _message(text: str, error: bool = False) -> None:
    print(text)
    if hou.isUIAvailable():
        hou.ui.displayMessage(
            text,
            title="Automated Texture Builder",
            severity=hou.severityType.Error if error else hou.severityType.Message,
        )


def _solaris_nodes(controller: hou.Node, with_assignment: bool):
    parent = controller.parent()
    requested = controller.evalParm("library_name").strip() or controller.name()
    owner = controller.path()
    library = next(
        (
            child for child in parent.children()
            if child.type().name() == "materiallibrary"
            and child.userData("automated_texture_builder") == "1"
            and child.userData("automated_texture_builder_controller") == owner
        ),
        None,
    )
    if library is None:
        candidate = parent.node(requested)
        if (
            candidate is not None
            and candidate.type().name() == "materiallibrary"
            and candidate.userData("automated_texture_builder") == "1"
        ):
            library = candidate
    if library is None:
        library = parent.createNode("materiallibrary", requested)
        library.setUserData("automated_texture_builder", "1")
    elif library.name() != requested:
        library.setName(requested, unique_name=True)
    library.setUserData("automated_texture_builder_controller", owner)
    library.setInput(0, controller)
    library.parm("matpathprefix").set("/materials/")
    library.parm("genpreviewshaders").set(1)
    library.setPosition(controller.position() + hou.Vector2(0.0, -2.0))
    assign = None
    final = library
    if with_assignment:
        assign_name = library.name() + "_assign"
        assign = parent.node(assign_name)
        if assign is None or assign.type().name() != "assignmaterial" or assign.userData("automated_texture_builder") != "1":
            assign = parent.createNode("assignmaterial", assign_name)
            assign.setUserData("automated_texture_builder", "1")
        assign.setInput(0, library)
        assign.setPosition(library.position() + hou.Vector2(0.0, -2.0))
        final = assign
    final.setDisplayFlag(True)
    return library, assign, final


def run(node: hou.Node) -> None:
    try:
        refresh_maketx_behavior(node)
        workflow = _menu(node, "texture_workflow")
        source_text = node.evalParm("texture_folder").strip()
        source = Path(source_text).expanduser() if source_text else None
        output = source / "tx" if source else None
        ocio = resolve_ocio(None if node.evalParm("use_houdini_ocio") else node.evalParm("ocio_config"))
        scene_linear = scene_linear_space(load_ocio(ocio))
        node.parm("scene_linear_space").set(scene_linear)
        node.parm("active_ocio_config").set(str(ocio))
        with hou.undos.group("Build automated textures and materials"):
            if workflow == "generate_tx":
                if source is None:
                    raise RuntimeError("Choose a Source Texture Folder for Generate / Update TX mode")
                manifest = convert(
                    source,
                    output,
                    ocio,
                    scene_linear,
                    bool(node.evalParm("force_rebuild")),
                    bool(node.evalParm("inspect_images")),
                )
            elif workflow == "existing_tx":
                if source is None:
                    raise RuntimeError("Choose the Texture Folder containing the existing TX files")
                manifest = manifest_existing_tx(
                    resolve_existing_tx_root(source), ocio, bool(node.evalParm("inspect_images"))
                )
            else:
                if source is None:
                    raise RuntimeError("Choose a Source Texture Folder for Source Images Direct mode")
                manifest = manifest_source_images(source, ocio, bool(node.evalParm("inspect_images")))
            _update_conversion_summary(node, manifest, workflow)
            auto = bool(node.evalParm("auto_assign"))
            library, assign, final = _solaris_nodes(node, auto)
            material_paths = build_materials(
                library,
                manifest,
                _menu(node, "builder_profile"),
                _menu(node, "surface_model"),
                _menu(node, "texture_mode"),
                "st",
            )
            matches = {}
            if auto:
                stage = node.inputs()[0].stage() if node.inputs() and node.inputs()[0] else node.stage()
                matches = auto_assign(assign, stage, material_paths, node.evalParm("geometry_root"))
            library.parent().layoutChildren(items=(library, assign) if assign else (library,))
        _message(
            f"Built {len(material_paths)} visible Solaris material subnet(s) in:\n{library.path()}\n"
            f"OCIO scene-linear: {scene_linear}\nManifest: {manifest}\n"
            f"Automatic assignments: {len(matches)}. Output node: {final.path()}"
        )
    except Exception as exc:
        summary = node.parm("conversion_summary")
        if summary is not None:
            summary.set(f"Failed: {exc}")
        traceback.print_exc()
        _message(str(exc), True)
        raise


def delete_sources(node: hou.Node) -> None:
    """Delete only verified source images from the last successful TX build."""
    workflow = _menu(node, "texture_workflow")
    if workflow == "source_direct":
        raise RuntimeError("Original source deletion is blocked while Use Source Images Directly is selected.")
    source_text = node.evalParm("texture_folder").strip()
    if not source_text:
        raise RuntimeError("Choose the source Texture Folder first.")
    try:
        source = Path(source_text).expanduser().resolve()
        if workflow == "generate_tx":
            deleted = delete_original_sources(source / "tx" / "automated_texture_manifest.json")
        else:
            deleted = delete_sources_for_existing_tx(source)
        node.parm("conversion_summary").set(
            f"Deleted {len(deleted)} verified original source texture file(s); generated TX files were preserved."
        )
        _message(
            f"Deleted {len(deleted)} original source texture file(s).\n"
            "Only files listed in the completed manifest were removed; generated TX files were preserved."
        )
    except Exception as exc:
        _message(str(exc), True)
        raise


def browse_folder(node: hou.Node, parm_name: str) -> None:
    if not hou.isUIAvailable():
        return
    value = hou.ui.selectFile(file_type=hou.fileType.Directory, chooser_mode=hou.fileChooserMode.Read)
    if value:
        node.parm(parm_name).set(value)
