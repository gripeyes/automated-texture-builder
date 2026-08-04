# Automated Texture Builder for Houdini 22

Converts Adobe Substance 3D Painter 12.1 texture sets to tiled,
mipmapped `.tx` files and builds USD materials for Karma and
Arnold. It supports multiple texture sets, UDIM discovery, OpenGL normal maps,
height/displacement, specular weight, anisotropy, OCIO file rules, and cautious
automatic USD material assignment.

## Install

Run the reusable installer whenever the tool is moved or Houdini is upgraded:

```sh
python3 /Users/j7s/coding/automated-texture-builder/scripts/install.py
```

The Houdini package file is installed at:

`~/Library/Preferences/houdini/22.0/packages/automated_texture_builder.json`

Restart Houdini 22, enter `/stage`, press Tab, and create **Automated Texture
Builder**. Choose the Painter export folder and click **Convert, Build and
Assign**. The controller creates a visible sibling Material Library LOP and one
material-builder subnet per texture set; generated materials are not hidden
inside the HDA.

`Use Current Houdini OCIO` is enabled by default and reads `$OCIO`. The TX
working space is resolved from the config's `scene_linear` role and displayed
immediately when the node is created or its OCIO selection changes; it is not
hard-coded. Disable the checkbox to choose another config. The Color Management
tab also shows the resolved config path and has a manual Refresh button.

The Color Management tab summarizes the selected source folder using the
active config's real file rules. EXR, TIFF, and PNG/JPEG color maps display
`detected source space → OCIO scene-linear`. Data maps display `Raw → Raw` and
are never color transformed. Existing-TX mode explicitly reports that no
source conversion will occur. Generated TX lookup reports that color pixels
are already baked to scene-linear and MaterialX image nodes read them as Raw,
preventing a second color transform.

## Texture workflow controls

- **Use Source Images Directly**: references native EXR/TIFF/PNG/JPEG textures
  without generating TX files. MaterialX image nodes receive each detected
  source colorspace; data maps remain Raw.
- **Generate / Update TX Files**: reads Texture Folder and writes TX files to
  its `tx` subfolder. The normal mode is incremental and preserves current
  outputs.
- **Use Existing TX Files**: treats Texture Folder as the existing TX root,
  or automatically uses its `tx` subfolder when present. It scans recursively,
  creates a fresh manifest, and never invokes `maketx`.
- **Regenerate All TX Files**: ignores modification-time checks, runs
  every source image through maketx, and replaces matching TX outputs. It is
  available only in Generate / Update TX mode.
- **Record OIIO Inspection**: disabled by default. When enabled, stores
  `oiiotool --info -v --stats` reports in the
  manifest. Conversion mode records before and after; existing-TX mode records
  the TX report only.
- **Texture Color Status**: reports the result of the latest run, including the
  number of color textures assigned to OCIO scene-linear, the number of data
  textures kept Raw, and whether all files completed successfully.
- **Delete Original Input Textures**: available in Generate / Update and Use
  Existing TX modes. It deletes only sources with one verified TX counterpart.
  It is disabled when Use Source Images Directly is selected.

Every HDA control has hover help with the same behavior described in context.

Texture discovery is recursive. A common root may contain sibling folders such
as `sculpt` and `room`; generated outputs preserve that relative hierarchy under
the common `tx` folder.

UDIM sets are auto-detected from 1001-style filename tokens. Automatic mode
uses ordinary MtlX Image nodes with `<UDIM>` paths. Repeating Texture mode uses
one shared MtlX USD Transform 2D for scale, rotation and translation, feeding
regular MtlX Image nodes with explicit periodic U/V wrapping.
Every image has an explicit UV connection; `st` is the default USD primvar.

Choose between OpenPBR Surface and MaterialX Standard Surface for the MaterialX
profiles. Builder choices include USD MaterialX, Karma, USD MaterialX (Arnold),
native Arnold Material Builder, and MoonRay DwaBase. The MoonRay profile follows
the verified `tallsculpt_textured_moonray_uv_fixed-2.hiplc` topology: metalness
and roughness connect directly from ImageMap without scalar conversion nodes.
The OpenPBR profile recognizes and connects the complete practical OpenPBR 1.1
texture set, not just the bundled preset's core maps. This includes base and
specular controls; transmission color, depth, scattering and dispersion;
thin-walled translucency; subsurface color, radius and anisotropy; fuzz; coat
color, roughness, anisotropy and coat normal; thin film; opacity; emission; and
explicit or angle-driven surface/coat tangents. Both the formal OpenPBR names
and Painter/legacy aliases such as `Metalness`, `Roughness`, `Anisotropy`,
`Sheen`, and `Translucency` are accepted.

OpenPBR MaterialX is the lossless target for this full parameter set. MaterialX
Standard Surface, native Arnold Standard Surface, and MoonRay DwaBase receive
the closest supported equivalents where their shader models differ. The tool
does not multiply ambient occlusion into base color: AO is a mesh/lighting map,
not an OpenPBR Surface input, and baking it into the shader would double the
effect in a path tracer.

Automatic assignment is off by default. When enabled, it prefers an exact mesh-name match,
then compares meaningful partial name tokens longest-first against USD Mesh and
GeomSubset names. Generic imported prefixes such as `shop_materialpath` are
ignored, and ambiguous equal-scoring matches are left unassigned.

## Painter preset

`presets/Automated Texture Builder - Rec2020 TX Pipeline.spexp` exports BaseColor,
Metalness, Roughness, OpenGL Normal, Height, OpenPBR SpecularWeight, and
OpenPBR Anisotropy. It has also been installed into Painter's user export
presets without replacing older presets.

The preset intentionally omits emissive. Its seven outputs are BaseColor,
BaseMetalness, SpecularWeight, SpecularRoughness,
SpecularRoughnessAnisotropy, Normal OpenGL, and Height. Painter can display
shorter filenames such as `Metalness`, `Roughness`, and `Anisotropy`; the tool
accepts both spellings.

The bundled preset is deliberately a compact hero-material default. If extra
OpenPBR channels are added to a Painter texture set and exported by an extended
or custom output template, the Houdini tool discovers and wires them without a
code change. Painter only writes channels that are present in the chosen export
template.

BaseColor, Metalness, Roughness, Normal, SpecularWeight, and Anisotropy export
as 16-bit half-float OpenEXR. Height exports as 32-bit float OpenEXR for the
hero displacement workflow. This avoids 8-bit stepping in smooth material
controls and gives TX conversion a consistent VFX source container. The
maketx stage keeps Height as float32 inside the tiled EXR `.tx`. Other EXR
material maps preserve half or float storage unless an OCIO color conversion
requires the source-aware policy described below.

For arbitrary downloaded or externally authored textures, TX storage is chosen
from both channel meaning and the pixel type reported by OpenImageIO. An 8-bit
sRGB PNG/JPEG color map is converted to scene-linear and stored as half-float;
this does not invent precision, but prevents the linearized result from being
quantized back to 8-bit. A 16-bit color source uses float32 during the OCIO
conversion. Untransformed Raw maps preserve uint8, uint16, half, or float
storage, while every height/displacement source is stored as float32. The
manifest and TX metadata record the detected source and selected output types.

## Command line

Run using Houdini's Python environment so PyOpenColorIO is available:

```sh
hython -m automated_texture_builder.cli /project/textures --force
```

The generated `automated_texture_manifest.json` records the OCIO config path and
SHA-256 checksum, source/output color spaces, UDIM sets, conversion status, and
OIIO inspection reports.
