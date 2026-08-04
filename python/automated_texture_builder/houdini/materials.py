from __future__ import annotations

import json
from pathlib import Path
import re

import hou
import voptoolutils


OPENPBR_INPUTS = {
    "base_weight": ("base_weight", "float"),
    "base_color": ("base_color", "color3"),
    "base_diffuse_roughness": ("base_diffuse_roughness", "float"),
    "base_metalness": ("base_metalness", "float"),
    "specular_weight": ("specular_weight", "float"),
    "specular_color": ("specular_color", "color3"),
    "specular_roughness": ("specular_roughness", "float"),
    "specular_ior": ("specular_ior", "float"),
    "specular_roughness_anisotropy": ("specular_roughness_anisotropy", "float"),
    "transmission_weight": ("transmission_weight", "float"),
    "transmission_color": ("transmission_color", "color3"),
    "transmission_depth": ("transmission_depth", "float"),
    "transmission_scatter": ("transmission_scatter", "color3"),
    "transmission_scatter_anisotropy": ("transmission_scatter_anisotropy", "float"),
    "transmission_dispersion_scale": ("transmission_dispersion_scale", "float"),
    "transmission_dispersion_abbe_number": ("transmission_dispersion_abbe_number", "float"),
    "translucency_weight": ("subsurface_weight", "float"),
    "translucency_color": ("subsurface_color", "color3"),
    "subsurface_weight": ("subsurface_weight", "float"),
    "subsurface_color": ("subsurface_color", "color3"),
    "subsurface_radius": ("subsurface_radius", "float"),
    "subsurface_radius_scale": ("subsurface_radius_scale", "color3"),
    "subsurface_scatter_anisotropy": ("subsurface_scatter_anisotropy", "float"),
    "fuzz_weight": ("fuzz_weight", "float"),
    "fuzz_color": ("fuzz_color", "color3"),
    "fuzz_roughness": ("fuzz_roughness", "float"),
    "coat_weight": ("coat_weight", "float"),
    "coat_color": ("coat_color", "color3"),
    "coat_roughness": ("coat_roughness", "float"),
    "coat_roughness_anisotropy": ("coat_roughness_anisotropy", "float"),
    "coat_ior": ("coat_ior", "float"),
    "coat_darkening": ("coat_darkening", "float"),
    "thin_film_weight": ("thin_film_weight", "float"),
    "thin_film_thickness": ("thin_film_thickness", "float"),
    "thin_film_ior": ("thin_film_ior", "float"),
    "emission_luminance": ("emission_luminance", "float"),
    "emission_color": ("emission_color", "color3"),
    "opacity": ("geometry_opacity", "float"),
}

STANDARD_INPUTS = {
    **{key: value for key, value in OPENPBR_INPUTS.items() if key not in {
        "base_weight", "base_diffuse_roughness", "base_metalness", "specular_weight",
        "specular_ior", "specular_roughness_anisotropy", "transmission_weight",
        "transmission_dispersion_scale", "transmission_dispersion_abbe_number",
        "translucency_weight", "translucency_color",
        "subsurface_weight", "subsurface_radius_scale", "subsurface_scatter_anisotropy",
        "fuzz_weight", "fuzz_color", "fuzz_roughness", "coat_weight",
        "coat_roughness_anisotropy", "coat_ior", "coat_darkening", "thin_film_weight",
        "emission_luminance", "opacity",
    }},
    "base_weight": ("base", "float"),
    "base_diffuse_roughness": ("diffuse_roughness", "float"),
    "base_metalness": ("metalness", "float"),
    "specular_weight": ("specular", "float"),
    "specular_ior": ("specular_IOR", "float"),
    "specular_roughness_anisotropy": ("specular_anisotropy", "float"),
    "specular_anisotropy_angle": ("specular_rotation", "float"),
    "transmission_weight": ("transmission", "float"),
    "transmission_dispersion_scale": ("transmission_dispersion", "float"),
    "translucency_weight": ("subsurface", "float"),
    "translucency_color": ("subsurface_color", "color3"),
    "subsurface_weight": ("subsurface", "float"),
    "subsurface_radius": ("subsurface_scale", "float"),
    "subsurface_radius_scale": ("subsurface_radius", "color3"),
    "subsurface_scatter_anisotropy": ("subsurface_anisotropy", "float"),
    "fuzz_weight": ("sheen", "float"),
    "fuzz_color": ("sheen_color", "color3"),
    "fuzz_roughness": ("sheen_roughness", "float"),
    "coat_weight": ("coat", "float"),
    "coat_roughness_anisotropy": ("coat_anisotropy", "float"),
    "coat_anisotropy_angle": ("coat_rotation", "float"),
    "coat_ior": ("coat_IOR", "float"),
    "thin_film_thickness": ("thin_film_thickness", "float"),
    "thin_film_ior": ("thin_film_IOR", "float"),
    "emission_luminance": ("emission", "float"),
    "opacity": ("opacity", "color3"),
}


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return value or "material"


def _input_index(node: hou.Node, name: str) -> int:
    try:
        return node.inputNames().index(name)
    except ValueError as exc:
        raise RuntimeError(f"{node.type().name()} has no input named {name}") from exc


def _connect(target: hou.Node, target_name: str, source: hou.Node) -> None:
    target.setInput(_input_index(target, target_name), source, 0)


def _connect_output(target: hou.Node, target_name: str, source: hou.Node, output_name: str) -> None:
    target.setInput(
        _input_index(target, target_name), source,
        source.outputNames().index(output_name),
    )


def _make_builder(library: hou.Node, name: str, profile: str) -> hou.Node:
    if profile == "karma":
        mask = voptoolutils.KARMAMTLX_TAB_MASK
        label, context = "Karma Material Builder", "kma"
    elif profile == "arnold":
        mask = "ArnoldMaterialX " + voptoolutils.MTLX_TAB_MASK
        label, context = "USD MaterialX Builder (Arnold)", "mtlx"
    else:
        mask = voptoolutils.MTLX_TAB_MASK
        label, context = "USD MaterialX Builder", "mtlx"
    builder = voptoolutils._setupMtlXBuilderSubnet(
        destination_node=library, name=name, mask=mask,
        folder_label=label, render_context=context,
    )
    builder.setName(name, unique_name=True)
    builder.setUserData("automated_texture_builder", "1")
    builder.setMaterialFlag(True)
    return builder


def _uv_node(builder: hou.Node, uv_primvar: str) -> hou.Node:
    if uv_primvar == "st":
        uv = builder.createNode("mtlxtexcoord", "uv_st")
    else:
        uv = builder.createNode("mtlxgeompropvalue", "uv_" + safe_name(uv_primvar))
        uv.parm("signature").set("vector2")
        uv.parm("geomprop").set(uv_primvar)
    uv.setPosition(hou.Vector2(-7.0, 1.0))
    return uv


def _image(
    parent: hou.Node, name: str, path: str, signature: str,
    uv: hou.Node, texture_mode: str, lookup_space: str = "Raw",
    uv_transform: hou.Node | None = None,
) -> hou.Node:
    node = parent.createNode("mtlximage", name)
    node.parm("signature").set(signature)
    node.parm("file").set(path)
    if node.parm("filecolorspace"):
        node.parm("filecolorspace").set(lookup_space)
    _connect(node, "texcoord", uv_transform if texture_mode == "repeat" and uv_transform else uv)
    if texture_mode == "repeat":
        node.parm("uaddressmode").set("periodic")
        node.parm("vaddressmode").set("periodic")
    return node


def _uv_transform_node(builder: hou.Node, uv: hou.Node) -> hou.Node:
    """One shared USD-compatible 2D transform for all repeating image maps."""
    transform = builder.createNode("mtlxUsdTransform2d", "uv_transform2d")
    _connect(transform, "in", uv)
    transform.parm("scalex").set(1.0)
    transform.parm("scaley").set(1.0)
    transform.parm("rotation").set(0.0)
    transform.parm("translationx").set(0.0)
    transform.parm("translationy").set(0.0)
    transform.setPosition(hou.Vector2(-7.0, -0.5))
    return transform


def _angle_to_tangent(builder: hou.Node, angle: hou.Node, name: str) -> hou.Node:
    """Convert Painter's normalized anisotropy angle into a tangent vector."""
    radians = builder.createNode("mtlxmultiply", name + "_radians")
    radians.parm("signature").set("float")
    radians.parm("in2").set(6.283185307179586)
    _connect(radians, "in1", angle)
    cosine = builder.createNode("mtlxcos", name + "_cos")
    sine = builder.createNode("mtlxsin", name + "_sin")
    _connect(cosine, "in", radians)
    _connect(sine, "in", radians)
    tangent = builder.createNode("mtlxtangent", name + "_basis_u")
    bitangent = builder.createNode("mtlxbitangent", name + "_basis_v")
    tangent_weighted = builder.createNode("mtlxmultiply", name + "_tangent_u")
    tangent_weighted.parm("signature").set("vector3FA")
    _connect(tangent_weighted, "in1", tangent)
    _connect(tangent_weighted, "in2", cosine)
    bitangent_weighted = builder.createNode("mtlxmultiply", name + "_tangent_v")
    bitangent_weighted.parm("signature").set("vector3FA")
    _connect(bitangent_weighted, "in1", bitangent)
    _connect(bitangent_weighted, "in2", sine)
    result = builder.createNode("mtlxadd", name + "_tangent")
    result.parm("signature").set("vector3")
    _connect(result, "in1", tangent_weighted)
    _connect(result, "in2", bitangent_weighted)
    return result


def clear_generated(library: hou.Node) -> None:
    for child in list(library.children()):
        if child.userData("automated_texture_builder") == "1":
            child.destroy()


def _publish_library(library: hou.Node, material_paths: dict[str, str]) -> dict[str, str]:
    count = library.parm("materials")
    if count is not None:
        count.set(len(material_paths))
        for index, set_name in enumerate(sorted(material_paths), 1):
            node_name = material_paths[set_name].rsplit("/", 1)[-1]
            for parm_name, value in (
                (f"enable{index}", 1), (f"matflag{index}", 0),
                (f"matnode{index}", node_name), (f"matpath{index}", node_name),
                (f"assign{index}", 0), (f"geopath{index}", ""),
            ):
                parm = library.parm(parm_name)
                if parm is not None:
                    parm.set(value)
    library.layoutChildren()
    return material_paths


def _arnold_image(builder: hou.Node, name: str, item: dict, texture_mode: str) -> hou.Node:
    image = builder.createNode("arnold::image", name)
    image.parm("filename").set(item["path"])
    image.parm("color_space").set(item.get("lookup_space", "Raw"))
    if texture_mode == "repeat":
        image.parm("swrap").set("periodic")
        image.parm("twrap").set("periodic")
    return image


def _build_arnold_native(
    library: hou.Node, data: dict, texture_mode: str,
) -> dict[str, str]:
    clear_generated(library)
    material_paths: dict[str, str] = {}
    mapping = {
        "base_weight": ("base", "r"),
        "base_color": ("base_color", "rgba"),
        "base_diffuse_roughness": ("diffuse_roughness", "r"),
        "base_metalness": ("metalness", "r"),
        "specular_weight": ("specular", "r"),
        "specular_color": ("specular_color", "rgba"),
        "specular_roughness": ("specular_roughness", "r"),
        "specular_ior": ("specular_IOR", "r"),
        "specular_roughness_anisotropy": ("specular_anisotropy", "r"),
        "specular_anisotropy_angle": ("specular_rotation", "r"),
        "transmission_weight": ("transmission", "r"),
        "transmission_color": ("transmission_color", "rgba"),
        "transmission_depth": ("transmission_depth", "r"),
        "transmission_scatter": ("transmission_scatter", "rgba"),
        "transmission_scatter_anisotropy": ("transmission_scatter_anisotropy", "r"),
        "transmission_dispersion_scale": ("transmission_dispersion", "r"),
        "translucency_weight": ("subsurface", "r"),
        "translucency_color": ("subsurface_color", "rgba"),
        "subsurface_weight": ("subsurface", "r"),
        "subsurface_color": ("subsurface_color", "rgba"),
        "subsurface_radius": ("subsurface_scale", "r"),
        "subsurface_radius_scale": ("subsurface_radius", "rgba"),
        "subsurface_scatter_anisotropy": ("subsurface_anisotropy", "r"),
        "fuzz_weight": ("sheen", "r"),
        "fuzz_color": ("sheen_color", "rgba"),
        "fuzz_roughness": ("sheen_roughness", "r"),
        "coat_weight": ("coat", "r"),
        "coat_color": ("coat_color", "rgba"),
        "coat_roughness": ("coat_roughness", "r"),
        "coat_roughness_anisotropy": ("coat_anisotropy", "r"),
        "coat_anisotropy_angle": ("coat_rotation", "r"),
        "coat_ior": ("coat_IOR", "r"),
        "thin_film_thickness": ("thin_film_thickness", "r"),
        "thin_film_ior": ("thin_film_IOR", "r"),
        "emission_luminance": ("emission", "r"),
        "emission_color": ("emission_color", "rgba"),
        "opacity": ("opacity", "rgba"),
    }
    for index, texture_set in enumerate(data["texture_sets"]):
        set_name = texture_set["name"]
        builder = library.createNode("arnold_materialbuilder", safe_name(set_name))
        builder.setUserData("automated_texture_builder", "1")
        surface = builder.createNode("arnold::standard_surface", "standard_surface")
        output = builder.node("OUT_material")
        _connect(output, "surface", surface)
        maps = texture_set["maps"]
        normal_node = None
        for offset, (channel, (input_name, output_name)) in enumerate(mapping.items()):
            if channel not in maps or input_name not in surface.inputNames():
                continue
            image = _arnold_image(builder, channel, maps[channel], texture_mode)
            image.setPosition(hou.Vector2(-4.5, 5.0 - offset * 1.0))
            _connect_output(surface, input_name, image, output_name)
        if "thin_walled" in maps or "translucency_weight" in maps or "translucency_color" in maps:
            parm = surface.parm("thin_walled")
            if parm is not None:
                parm.set(1)
        if "normal" in maps:
            image = _arnold_image(builder, "normal_image", maps["normal"], texture_mode)
            image.parm("color_space").set("Raw")
            normal = builder.createNode("arnold::normal_map", "normal")
            _connect_output(normal, "input", image, "rgba")
            _connect(surface, "normal", normal)
            normal_node = normal
        if "coat_normal" in maps and "coat_normal" in surface.inputNames():
            image = _arnold_image(builder, "coat_normal_image", maps["coat_normal"], texture_mode)
            image.parm("color_space").set("Raw")
            coat_normal = builder.createNode("arnold::normal_map", "coat_normal")
            _connect_output(coat_normal, "input", image, "rgba")
            _connect(surface, "coat_normal", coat_normal)
        if "height" in maps:
            image = _arnold_image(builder, "height", maps["height"], texture_mode)
            image.parm("color_space").set("Raw")
            bump = builder.createNode("arnold::bump2d", "height_bump")
            _connect_output(bump, "bump_map", image, "r")
            if normal_node is not None:
                _connect(bump, "normal", normal_node)
            _connect(surface, "normal", bump)
        builder.layoutChildren()
        builder.setPosition(hou.Vector2(float(index % 4) * 4.0, -float(index // 4) * 3.0))
        material_paths[set_name] = "/materials/" + builder.name()
    return _publish_library(library, material_paths)


MOONRAY_TYPES = {
    "base": "Vop::DW_MOONRAY::DwaBaseMaterial::1",
    "image": "Vop::DW_MOONRAY::ImageMap::1",
    "normal": "Vop::DW_MOONRAY::ImageNormalMap::1",
    "to_float": "Vop::DW_MOONRAY::MultiChannelToFloatMap::1",
    "displacement": "Vop::DW_MOONRAY::NormalDisplacement::1",
}


def _ensure_moonray_types() -> None:
    if hou.nodeType(hou.vopNodeTypeCategory(), MOONRAY_TYPES["base"]) is not None:
        return
    roots = [
        Path("/Applications/MoonRay/installs/openmoonray/plugin/houdini/otls"),
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for node_type in MOONRAY_TYPES.values():
            asset = root / f"{node_type}.hda"
            if asset.is_file():
                hou.hda.installFile(str(asset))
    if hou.nodeType(hou.vopNodeTypeCategory(), MOONRAY_TYPES["base"]) is None:
        raise RuntimeError("MoonRay Houdini shader assets are not installed or available.")


def _moonray_connector(builder: hou.Node, name: str, label: str, parmtype: int) -> hou.Node:
    connector = builder.createNode("subnetconnector", name + "_output")
    connector.parm("connectorkind").set(1)
    connector.parm("parmname").set(name)
    connector.parm("parmlabel").set(label)
    connector.parm("parmtype").set(parmtype)
    return connector


def _moonray_image(
    builder: hou.Node, name: str, item: dict, texture_mode: str,
) -> hou.Node:
    image = builder.createNode(MOONRAY_TYPES["image"], name)
    image.parm("texture").set(item["path"])
    lookup_space = item.get("lookup_space", "Raw")
    image.parm("source_color_space").set(
        "raw" if lookup_space.casefold() == "raw" else lookup_space
    )
    image.parm("wrap_around").set(1 if texture_mode == "repeat" else 0)
    return image


def _build_moonray(
    library: hou.Node, data: dict, texture_mode: str,
) -> dict[str, str]:
    _ensure_moonray_types()
    clear_generated(library)
    material_paths: dict[str, str] = {}
    scalar_mapping = {
        "base_diffuse_roughness": "diffuse_roughness",
        "base_metalness": "metallic",
        "specular_weight": "specular",
        "specular_roughness": "roughness",
        "specular_ior": "refractive_index",
        "specular_roughness_anisotropy": "anisotropy",
        "transmission_weight": "transmission",
        "transmission_dispersion_abbe_number": "dispersion_abbe_number",
        "translucency_weight": "diffuse_transmission",
        "subsurface_radius": "scattering_radius",
        "fuzz_weight": "fuzz",
        "fuzz_roughness": "fuzz_roughness",
        "coat_weight": "clearcoat",
        "coat_roughness": "clearcoat_roughness",
        "coat_ior": "clearcoat_refractive_index",
        "thin_film_weight": "iridescence",
        "thin_film_thickness": "iridescence_thickness",
        "opacity": "presence",
    }
    color_mapping = {
        "transmission_color": "transmission_color",
        "translucency_color": "diffuse_transmission_color",
        "subsurface_color": "scattering_color",
        "fuzz_color": "fuzz_albedo",
        "coat_color": "clearcoat_attenuation_color",
        "emission_color": "emission",
    }
    for index, texture_set in enumerate(data["texture_sets"]):
        set_name = texture_set["name"]
        builder = library.createNode("subnet", safe_name(set_name))
        builder.setUserData("automated_texture_builder", "1")
        builder.setMaterialFlag(True)
        surface = builder.createNode(MOONRAY_TYPES["base"], "dwa_base")
        surface_output = _moonray_connector(builder, "surface", "Surface", 24)
        _connect(surface_output, "suboutput", surface)
        maps = texture_set["maps"]
        if "base_color" in maps:
            basecolor = _moonray_image(builder, "basecolor", maps["base_color"], texture_mode)
            _connect(surface, "albedo", basecolor)
            _connect(surface, "metallic_color", basecolor)
        for channel, input_name in scalar_mapping.items():
            if channel in maps:
                image = _moonray_image(builder, channel + "_image", maps[channel], texture_mode)
                # Direct Map-to-float connections match the verified fixed scene.
                _connect(surface, input_name, image)
        if "transmission_dispersion_abbe_number" in maps:
            surface.parm("use_dispersion").set(1)
        if "thin_walled" in maps or "translucency_weight" in maps or "translucency_color" in maps:
            surface.parm("thin_geometry").set(1)
        for channel, input_name in color_mapping.items():
            if channel in maps:
                image = _moonray_image(builder, channel + "_image", maps[channel], texture_mode)
                _connect(surface, input_name, image)
        if "normal" in maps:
            normal = builder.createNode(MOONRAY_TYPES["normal"], "normal")
            normal.parm("tangent_space_normal_texture").set(maps["normal"]["path"])
            normal.parm("normal_encoding").set("[0,1]")
            normal.parm("wrap_around").set(1 if texture_mode == "repeat" else 0)
            _connect(surface, "input_normal", normal)
        if "height" in maps:
            height_image = _moonray_image(builder, "height_image", maps["height"], texture_mode)
            height_red = builder.createNode(MOONRAY_TYPES["to_float"], "height_red")
            displacement = builder.createNode(MOONRAY_TYPES["displacement"], "height_displacement")
            displacement_output = _moonray_connector(builder, "displacement", "Displacement", 25)
            _connect(height_red, "input", height_image)
            _connect(displacement, "height", height_red)
            _connect(displacement_output, "suboutput", displacement)
        builder.layoutChildren()
        builder.setPosition(hou.Vector2(float(index % 4) * 4.0, -float(index // 4) * 3.0))
        material_paths[set_name] = "/materials/" + builder.name()
    return _publish_library(library, material_paths)


def _replace_surface(builder: hou.Node, surface_model: str) -> hou.Node:
    old = builder.node("mtlxstandard_surface")
    if surface_model == "standard_surface":
        old.setName("standard_surface", unique_name=True)
        return old
    surface = builder.createNode("mtlxopen_pbr_surface", "openpbr_surface")
    for connection in old.outputConnections():
        connection.outputNode().setInput(connection.inputIndex(), surface, connection.outputIndex())
    old.destroy()
    return surface


def build_materials(
    library: hou.Node,
    manifest_path: Path,
    profile: str = "generic",
    surface_model: str = "openpbr",
    texture_mode: str = "auto",
    uv_primvar: str = "st",
) -> dict[str, str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if profile == "arnold_native":
        return _build_arnold_native(library, data, texture_mode)
    if profile == "moonray":
        return _build_moonray(library, data, texture_mode)
    clear_generated(library)
    material_paths: dict[str, str] = {}
    input_map = OPENPBR_INPUTS if surface_model == "openpbr" else STANDARD_INPUTS
    for index, texture_set in enumerate(data["texture_sets"]):
        set_name = texture_set["name"]
        node_name = safe_name(set_name)
        builder = _make_builder(library, node_name, profile)
        surface = _replace_surface(builder, surface_model)
        surface.setPosition(hou.Vector2(1.0, 1.0))
        displacement = builder.node("mtlxdisplacement")
        uv = _uv_node(builder, uv_primvar)
        uv_transform = _uv_transform_node(builder, uv) if texture_mode == "repeat" else None
        maps = texture_set["maps"]
        for offset, (channel, (input_name, signature)) in enumerate(input_map.items()):
            if channel not in maps or input_name not in surface.inputNames():
                continue
            path = maps[channel]["path"]
            mode = "repeat" if texture_mode == "repeat" else "image"
            image = _image(
                builder, channel, path, signature, uv, mode,
                maps[channel].get("lookup_space", "Raw"),
                uv_transform,
            )
            image.setPosition(hou.Vector2(-4.5, 5.0 - offset * 1.1))
            _connect(surface, input_name, image)
        if surface_model == "openpbr":
            for channel, input_name in (
                ("tangent", "geometry_tangent"),
                ("coat_tangent", "geometry_coat_tangent"),
            ):
                if channel not in maps:
                    continue
                tangent = _image(
                    builder, channel, maps[channel]["path"], "vector3", uv,
                    texture_mode, "Raw", uv_transform,
                )
                _connect(surface, input_name, tangent)
            for channel, input_name in (
                ("specular_anisotropy_angle", "geometry_tangent"),
                ("coat_anisotropy_angle", "geometry_coat_tangent"),
            ):
                explicit_tangent = "tangent" if channel == "specular_anisotropy_angle" else "coat_tangent"
                if channel not in maps or explicit_tangent in maps:
                    continue
                angle = _image(
                    builder, channel, maps[channel]["path"], "float", uv,
                    texture_mode, "Raw", uv_transform,
                )
                _connect(surface, input_name, _angle_to_tangent(builder, angle, channel))
        thin_walled_input = "geometry_thin_walled" if surface_model == "openpbr" else "thin_walled"
        if "thin_walled" in maps:
            mask = _image(
                builder, "thin_walled", maps["thin_walled"]["path"], "float",
                uv, texture_mode, "Raw", uv_transform,
            )
            compare = builder.createNode("mtlxcompare", "thin_walled_threshold")
            compare.parm("test").set(3)  # greater than
            compare.parm("input2").set(0.5)
            _connect(compare, "input1", mask)
            _connect(surface, thin_walled_input, compare)
        elif "translucency_weight" in maps or "translucency_color" in maps:
            parm = surface.parm(thin_walled_input)
            if parm is not None:
                parm.set(1)
        if "legacy_specular_level" in maps and "specular_weight" not in maps:
            surface.setComment(
                "Legacy SpecularLevel was not connected. Export OpenPBR SpecularWeight instead."
            )
        if "normal" in maps:
            image = _image(
                builder, "normal_image", maps["normal"]["path"], "vector3",
                uv, texture_mode, "Raw", uv_transform,
            )
            normal = builder.createNode("mtlxnormalmap", "normal")
            image.setPosition(hou.Vector2(-4.5, -3.0))
            normal.setPosition(hou.Vector2(-1.5, -3.0))
            _connect(normal, "in", image)
            _connect(surface, "geometry_normal" if surface_model == "openpbr" else "normal", normal)
        if "coat_normal" in maps:
            image = _image(
                builder, "coat_normal_image", maps["coat_normal"]["path"], "vector3",
                uv, texture_mode, "Raw", uv_transform,
            )
            normal = builder.createNode("mtlxnormalmap", "coat_normal")
            _connect(normal, "in", image)
            _connect(surface, "geometry_coat_normal" if surface_model == "openpbr" else "coat_normal", normal)
        if "height" in maps:
            height = _image(
                builder, "height", maps["height"]["path"], "float",
                uv, texture_mode, "Raw", uv_transform,
            )
            height.setPosition(hou.Vector2(-4.5, -5.0))
            displacement.setPosition(hou.Vector2(-1.5, -5.0))
            _connect(displacement, "displacement", height)
        builder.layoutChildren()
        builder.setPosition(hou.Vector2(float(index % 4) * 4.0, -float(index // 4) * 3.0))
        material_paths[set_name] = "/materials/" + builder.name()
    return _publish_library(library, material_paths)


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def auto_assign(library: hou.Node, stage, material_paths: dict[str, str], geometry_root: str) -> dict[str, str]:
    candidates = []
    root = stage.GetPrimAtPath(geometry_root) if geometry_root else stage.GetPseudoRoot()
    if root:
        for prim in stage.Traverse():
            path = str(prim.GetPath())
            if (not geometry_root or path.startswith(geometry_root)) and prim.GetTypeName() in {"Mesh", "GeomSubset"}:
                candidates.append(path)
    matches: dict[str, str] = {}
    for set_name in material_paths:
        set_key = normalize(set_name)
        ranked = []
        for path in candidates:
            prim_name = path.rsplit("/", 1)[-1]
            prim_key = normalize(prim_name)
            if prim_key == set_key:
                ranked.append((3, len(prim_key), path))
                continue
            terms = [
                normalize(term)
                for term in re.split(r"[_\-.\s]+", prim_name)
                if len(normalize(term)) >= 4
                and normalize(term) not in {"shop", "path", "material", "materialpath", "shopmaterialpath"}
            ]
            matching_terms = [term for term in terms if term in set_key]
            if matching_terms:
                ranked.append((2, max(map(len, matching_terms)), path))
            elif min(len(prim_key), len(set_key)) >= 6 and (prim_key in set_key or set_key in prim_key):
                ranked.append((1, min(len(prim_key), len(set_key)), path))
        if ranked:
            best_rank = max((rank, length) for rank, length, _ in ranked)
            best = [path for rank, length, path in ranked if (rank, length) == best_rank]
            if len(best) == 1:
                matches[set_name] = best[0]
    # Material Library uses the same sorted order authored by _publish_library.
    # Bind directly in each material entry instead of creating another LOP.
    for index, set_name in enumerate(sorted(material_paths), 1):
        assigned_path = matches.get(set_name, "")
        library.parm(f"assign{index}").set(1 if assigned_path else 0)
        library.parm(f"geopath{index}").set(assigned_path)
    return matches
