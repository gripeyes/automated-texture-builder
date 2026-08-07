#!/usr/bin/env hython
"""Create the Houdini 22 Automated Texture Builder LOP HDA."""

from __future__ import annotations

from pathlib import Path

import hou


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "otls" / "automated_texture_builder.hda"
TYPE_NAME = "j7s::automated_texture_builder::1.0"


def callback_code(call: str) -> str:
    """Reload editable tool modules so an open Houdini uses the current build."""
    return (
        "import importlib; import automated_texture_builder.discovery as d; "
        "importlib.reload(d); import automated_texture_builder.geometry_detail as gd; "
        "importlib.reload(gd); import automated_texture_builder.matching as mt; "
        "importlib.reload(mt); import automated_texture_builder.conversion as cv; "
        "importlib.reload(cv); import automated_texture_builder.houdini.materials as m; "
        "importlib.reload(m); import automated_texture_builder.houdini.callbacks as c; "
        f"importlib.reload(c); {call}"
    )


def button(name: str, label: str, callback: str) -> hou.ButtonParmTemplate:
    parm = hou.ButtonParmTemplate(name, label)
    parm.setScriptCallback(callback)
    parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return parm


def explained(parm: hou.ParmTemplate, text: str) -> hou.ParmTemplate:
    parm.setHelp(text)
    return parm


def refresh_callback(parm: hou.ParmTemplate) -> hou.ParmTemplate:
    parm.setScriptCallback(callback_code("c.refresh_scene_linear(kwargs['node'])"))
    parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return parm


def python_callback(parm: hou.ParmTemplate, function_name: str) -> hou.ParmTemplate:
    parm.setScriptCallback(callback_code(f"c.{function_name}(kwargs['node'])"))
    parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return parm


def compact_info(name: str, label: str, value: str) -> hou.StringParmTemplate:
    parm = hou.StringParmTemplate(name, label, 1, (value,))
    parm.setConditional(hou.parmCondType.DisableWhen, "{ use_houdini_ocio >= 0 }")
    return parm


def build() -> Path:
    OUTPUT.unlink(missing_ok=True)
    stage = hou.node("/stage")
    controller = stage.createNode("subnet", "automated_texture_builder_source")
    hda = controller.createDigitalAsset(
        name=TYPE_NAME,
        hda_file_name=str(OUTPUT),
        description="Automated Texture Builder",
        min_num_inputs=0,
        max_num_inputs=1,
        version="1.0",
        save_as_embedded=False,
        ignore_external_references=True,
    )
    hda.allowEditingOfContents()
    output = hda.node("output0") or hda.createNode("output", "output0")
    indirect_inputs = hda.indirectInputs()
    if indirect_inputs:
        output.setInput(0, indirect_inputs[0])
    hda.layoutChildren()
    definition = hda.type().definition()
    group = hou.ParmTemplateGroup()

    textures = hou.FolderParmTemplate("builder", "Build")
    workflow = python_callback(hou.MenuParmTemplate(
        "texture_workflow", "Texture Workflow",
        ("source_direct", "generate_tx", "existing_tx"),
        ("Use Source Images Directly", "Generate / Update TX Files", "Use Existing TX Files"),
        default_value=1,
    ), "refresh_maketx_behavior")
    textures.addParmTemplate(explained(
        workflow,
        "Choose exactly one input workflow. Source Direct uses native images without maketx. Generate / Update creates TX incrementally. Existing TX scans a preconverted TX folder and never runs maketx.",
    ))
    texture_folder = hou.StringParmTemplate(
        "texture_folder", "Texture Folder", 1,
        string_type=hou.stringParmType.FileReference,
    )
    texture_folder.setFileType(hou.fileType.Directory)
    python_callback(texture_folder, "refresh_color_rules")
    textures.addParmTemplate(explained(
        texture_folder,
        "Source Direct and Generate / Update: choose the source texture folder. Existing TX: choose the folder containing .tx files. Generated TX files always go into a tx subfolder beside the sources.",
    ))
    force = python_callback(
        hou.ToggleParmTemplate("force_rebuild", "Regenerate All TX Files", False),
        "refresh_maketx_behavior",
    )
    force.setConditional(
        hou.parmCondType.DisableWhen,
        "{ texture_workflow != generate_tx }",
    )
    textures.addParmTemplate(explained(
        force,
        "Available only in Generate / Update TX mode. Enabled replaces every matching TX output. Disabled performs the normal incremental build and preserves current outputs.",
    ))
    textures.addParmTemplate(explained(
        compact_info(
            "maketx_behavior", "Texture Processing",
            "Incremental TX: missing, outdated, or incorrectly stored TX files are generated.",
        ),
        "Live explanation of the selected source/TX workflow. Incremental mode also rebuilds a TX whose stored pixel type does not match the source-aware precision policy.",
    ))
    textures.addParmTemplate(explained(
        hou.ToggleParmTemplate("inspect_images", "Record OIIO Inspection", False),
        "Runs oiiotool info and pixel statistics. Generate mode records source and TX reports; direct-source and existing-TX modes inspect the files they use. It can take longer.",
    ))
    textures.addParmTemplate(explained(
        compact_info(
            "conversion_summary", "Texture Color Status",
            "Not run yet.",
        ),
        "Result of the latest run, calculated from the generated manifest. This reports color and data texture counts and whether the operation completed successfully.",
    ))
    textures.addParmTemplate(hou.SeparatorParmTemplate("sep_material"))
    textures.addParmTemplate(explained(hou.MenuParmTemplate(
        "builder_profile", "Solaris Material Builder",
        ("generic", "karma", "arnold", "arnold_native", "moonray"),
        (
            "USD MaterialX Builder", "Karma Material Builder",
            "USD MaterialX Builder (Arnold)", "Arnold Material Builder",
            "MoonRay DwaBase Material Builder",
        ),
        default_value=0,
    ), "Chooses the actual Houdini material subnet created inside the external Solaris Material Library. Native Arnold creates Arnold Standard Surface; MoonRay creates the verified DwaBase topology."))
    surface_model = hou.MenuParmTemplate(
        "surface_model", "Surface Model",
        ("openpbr", "standard_surface"),
        ("OpenPBR Surface", "MaterialX Standard Surface"),
        default_value=0,
    )
    surface_model.setConditional(
        hou.parmCondType.DisableWhen,
        "{ builder_profile == arnold_native } { builder_profile == moonray }",
    )
    textures.addParmTemplate(explained(
        surface_model,
        "Applies to the three MaterialX builder profiles. Native Arnold uses Arnold Standard Surface; MoonRay uses DwaBaseMaterial.",
    ))
    textures.addParmTemplate(explained(hou.MenuParmTemplate(
        "texture_mode", "Texture Mode",
        ("auto", "repeat", "hex", "triplanar", "triplanar_breakup"),
        (
            "Automatic / UDIM",
            "Repeating Texture (USD Transform 2D)",
            "Tiled Texture with Hex Pattern Breakup",
            "Triplanar Projection",
            "Triplanar with Pattern Breakup",
        ),
        default_value=0,
    ), "Automatic / UDIM uses UVs and replaces 1001-style tiles with <UDIM>. Repeating mode shares one MtlX USD Transform 2D. Hex Pattern Breakup reduces repetition in UV-mapped materials. Triplanar projects in object space without requiring UVs. Breakup modes create one visible texture_controls node that drives all compatible lookups. USD MaterialX profiles use only standard MaterialX nodes; no Karma shader compound is inserted."))
    textures.addParmTemplate(explained(hou.MenuParmTemplate(
        "geometry_detail_mode", "Height / Displacement Mode",
        ("auto", "bump", "displacement", "off"),
        (
            "Automatic by Texture Name", "Bump Only",
            "True Displacement", "Ignore Height / Displacement",
        ),
        default_value=0,
    ), "Automatic uses the best available true-displacement signal in this order: Vector Displacement, Displacement, then Height. This matches Substance Painter, whose displacement source defaults to Height. Bump Only never changes the silhouette. Ignore leaves geometry detail disconnected."))
    textures.addParmTemplate(explained(hou.FloatParmTemplate(
        "bump_scale", "Bump Scale", 1, (1.0,),
    ), "Dimensionless strength used only in Bump Only mode. This changes shading normals without moving the mesh silhouette."))
    textures.addParmTemplate(explained(hou.FloatParmTemplate(
        "height_scale", "Displacement Scale (Scene Units)", 1, (0.01,),
    ), "Physical strength for scalar or vector true displacement. Painter texture pixels do not contain a reliable real-world distance, so adjust this for the asset's scene scale."))
    textures.addParmTemplate(explained(hou.FloatParmTemplate(
        "height_zero", "Height Zero Level", 1, (0.0,),
    ), "Texture value that leaves the surface unchanged. The included floating-point Substance Painter preset preserves signed height around 0. Use 0.5 for a conventional normalized black-to-white height map whose neutral value is middle gray."))
    textures.addParmTemplate(explained(compact_info(
        "height_note", "Height Handling",
        "Auto: Vector Displacement → Displacement → Height; one true-displacement input.",
    ), "Scalar true displacement is centered around the zero level and multiplied by the explicit scale. True displacement also requires suitable tessellation and displacement bounds on the rendered geometry."))
    textures.addParmTemplate(explained(hou.StringParmTemplate(
        "library_name", "Material Library Name", 1, ("$OS",)
    ), "Name of the visible sibling Material Library LOP created in /stage. $OS follows the Automated Texture Builder node name; Houdini adds a numeric suffix when a sibling already uses that exact name."))
    textures.addParmTemplate(hou.SeparatorParmTemplate("sep_assignment"))
    auto_assign = hou.ToggleParmTemplate("auto_assign", "Assign to Matching USD Meshes", False)
    auto_assign.setScriptCallback(callback_code("c.update_assignments(kwargs['node'])"))
    auto_assign.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    textures.addParmTemplate(explained(
        auto_assign,
        "Enables Assign to Geometry inside each generated Material Library entry for the best unique name match. Longer matching strings are preferred; ambiguous equal matches remain unassigned.",
    ))
    root = hou.StringParmTemplate("geometry_root", "USD Geometry Root", 1, ("/",))
    root.setConditional(hou.parmCondType.DisableWhen, "{ auto_assign == 0 }")
    root.setScriptCallback(callback_code("c.update_assignments(kwargs['node'])"))
    root.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    root.setTags({
        "script_action": "import loputils\nloputils.selectPrimsInParm(kwargs, True, allowinstanceproxies=True)",
        "script_action_help": "Select primitives in the Scene Viewer or Scene Graph Tree pane.\nCtrl-click to select using the primitive picker dialog.\nShift-click to select using the primitive pattern editor.",
        "script_action_icon": "BUTTONS_reselect",
        "sidefx::usdpathtype": "primlist",
    })
    textures.addParmTemplate(explained(
        root,
        "Limits automatic matching to this USD hierarchy. Use / for the whole stage or a path such as /World/Character.",
    ))
    textures.addParmTemplate(explained(compact_info(
        "assignment_note", "Automatic Assignment",
        "Matches complete names first, prefers geometry subsets, and validates UDIM st/uv coordinates.",
    ), "Numeric suffixes are preserved, imported prefixes are ignored, and partial matches are checked from longest to shortest. Missing UDIM tiles or st/uv primvars are reported here after the build."))
    textures.addParmTemplate(explained(button(
        "run_all", "Convert, Build and Assign",
        callback_code("c.run(kwargs['node'])"),
    ), "Runs the selected texture workflow, then creates visible Solaris material subnetworks and optionally assigns them."))
    textures.addParmTemplate(hou.SeparatorParmTemplate("sep_delete_sources"))
    delete_button = button(
        "delete_sources", "Delete Original Input Textures",
        callback_code("c.delete_sources(kwargs['node'])"),
    )
    delete_button.setConditional(
        hou.parmCondType.DisableWhen,
        "{ texture_workflow == source_direct }",
    )
    textures.addParmTemplate(explained(
        delete_button,
        "Permanently deletes only source textures with a verified generated or existing TX counterpart. It is disabled only when Use Source Images Directly is selected.",
    ))
    group.append(textures)

    color = hou.FolderParmTemplate("color_management", "Color Management")
    tx_rule = hou.StringParmTemplate(
        "rule_tx", "TX Rule Check", 1, ("Refreshing...",),
    )
    tx_rule.setConditional(hou.parmCondType.DisableWhen, "{ use_houdini_ocio >= 0 }")
    color.addParmTemplate(explained(
        tx_rule,
        "Top-priority double-transform safety check. The active OCIO .tx file rule must resolve to Raw because color TX pixels are already baked into scene-linear during conversion.",
    ))
    use_ocio = refresh_callback(hou.ToggleParmTemplate("use_houdini_ocio", "Use Current Houdini OCIO", True))
    color.addParmTemplate(explained(
        use_ocio,
        "Uses the OCIO config currently active in Houdini through $OCIO. Disable this to select a different config below.",
    ))
    ocio = hou.StringParmTemplate("ocio_config", "OCIO Config", 1, string_type=hou.stringParmType.FileReference)
    ocio.setFileType(hou.fileType.Any)
    ocio.setConditional(hou.parmCondType.DisableWhen, "{ use_houdini_ocio == 1 }")
    refresh_callback(ocio)
    color.addParmTemplate(explained(
        ocio,
        "Alternate OCIO config. Its scene_linear role is read automatically; selecting ACES should normally display ACEScg when that config assigns ACEScg to scene_linear.",
    ))
    active = hou.StringParmTemplate("active_ocio_config", "Active OCIO Config", 1, ("Refreshing...",))
    active.setConditional(hou.parmCondType.DisableWhen, "{ use_houdini_ocio >= 0 }")
    color.addParmTemplate(explained(active, "Resolved config used by the tool. This field is informational."))
    scene = hou.StringParmTemplate("scene_linear_space", "Detected OCIO Scene-Linear", 1, ("Refreshing...",))
    scene.setConditional(hou.parmCondType.DisableWhen, "{ use_houdini_ocio >= 0 }")
    color.addParmTemplate(explained(
        scene,
        "Color space assigned to the selected config's scene_linear role. Color textures are converted to this space; data textures remain Raw.",
    ))
    skip_web = refresh_callback(hou.ToggleParmTemplate(
        "skip_web_linearization",
        "Skip PNG/JPEG Color Linearization",
        False,
    ))
    skip_web.setConditional(
        hou.parmCondType.DisableWhen,
        "{ texture_workflow != generate_tx }",
    )
    color.addParmTemplate(explained(
        skip_web,
        "Advanced exception for PNG/JPEG color maps whose pixels are already scene-linear despite being classified as display-referred. Matching display-referred maps bypass OCIO conversion and are stored in TX as Raw. Explicit OCIO filename/path rules that identify linear or log inputs remain authoritative. Leave this off for downloaded textures and normal Substance color exports, which are usually sRGB-encoded.",
    ))
    color.addParmTemplate(hou.SeparatorParmTemplate("sep_file_rules"))
    color.addParmTemplate(hou.LabelParmTemplate(
        "file_rules_heading",
        "Detected source-file read rules",
    ))
    for name, label, help_text in (
        ("rule_exr", "EXR Color Textures", "OCIO colorspace used to read recognized EXR color maps. This is separate from the TX conversion target."),
        ("rule_tiff", "TIFF Color Textures", "OCIO colorspace used to read recognized TIFF color maps. This is separate from the TX conversion target."),
        ("rule_web", "PNG / JPEG Color Textures", "OCIO colorspace selected from the full file path. Specific name/path rules are evaluated before the extension fallback. These color maps are normally read as sRGB and converted to scene-linear during TX generation."),
        ("rule_data", "Data Maps", "Metalness, roughness, specular weight, normals, height and other numeric maps remain Raw and receive no color transform."),
        ("rule_target", "TX Color Texture Target", "Destination for color pixels when Generate / Update TX mode is selected. This follows OCIO's scene_linear role, such as ACEScg."),
    ):
        rule = hou.StringParmTemplate(name, label, 1, ("Refreshing...",))
        rule.setConditional(hou.parmCondType.DisableWhen, "{ use_houdini_ocio >= 0 }")
        color.addParmTemplate(explained(rule, help_text))
    color.addParmTemplate(explained(button(
        "refresh_ocio", "Refresh OCIO Detection",
        callback_code("c.refresh_scene_linear(kwargs['node'], True)"),
    ), "Refreshes the active config path and scene_linear role without converting textures or building materials."))
    color.addParmTemplate(explained(compact_info(
        "ocio_dev_note", "Dev note",
        "Don't be changing any of this unless you know what and why you're doing something here.",
    ), "Color-management changes affect texture interpretation and can cause double transforms."))
    group.append(color)
    definition.setParmTemplateGroup(group)
    definition.setExtraFileOption("OnCreated/IsPython", True)
    definition.addSection(
        "OnCreated",
        callback_code(
            "c.refresh_scene_linear(kwargs['node']); "
            "c.refresh_maketx_behavior(kwargs['node'])"
        ) + "\n",
    )
    definition.addSection(
        "Help",
        """= Automated Texture Builder =

Turns a texture folder into ready-to-use material subnetworks in Solaris.

Quick start:
1. Choose Source Direct, Generate / Update TX, or Existing TX.
2. Select the texture folder.
3. Choose the renderer material builder and surface model.
4. Choose Automatic / UDIM or Repeating Tiled Image.
5. Click Convert, Build and Assign.

The tool groups matching textures, optionally creates render-ready TX files,
and creates one visible material subnetwork per texture set in a sibling
Material Library LOP. It recognizes the core PBR maps plus OpenPBR transmission,
translucency, subsurface, fuzz, coat, thin-film, opacity, emission, normals,
tangents and displacement.

Choose OpenPBR Surface or MaterialX Standard Surface, and choose a generic,
Karma, Arnold, native Arnold, or MoonRay material builder. UV-based textures
get an explicit UV connection. Automatic/UDIM mode detects 1001-style tiles;
Repeating mode adds a shared MtlX USD Transform 2D. Triplanar modes project
textures in object space without UVs; the breakup variant uses one shared,
renderer-neutral MaterialX position graph and a visible texture-controls node.
Hex Pattern Breakup adds MaterialX 1.39 hex image and normal-map lookups to
reduce obvious UV repetition.

Leave Houdini OCIO enabled unless the project requires another config. Color
maps are converted to scene-linear; data maps and completed TX files stay Raw.
Input bit depth is detected automatically and displacement is stored float32.

Automatic USD assignment is off by default. When enabled, it fills the Assign
to Geometry fields inside the generated Material Library. It matches exact names
first and then tries unique partial names longest-first. Ambiguous matches are
skipped; no separate Assign Material LOP is created.
""",
    )
    definition.updateFromNode(hda)
    hda.destroy()
    hou.hda.installFile(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    print(build())
