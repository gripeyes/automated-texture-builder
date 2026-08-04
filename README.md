# Automated Texture Builder for Houdini 22

Automated Texture Builder turns a folder of textures into ready-to-use material
subnetworks in Solaris.

It finds the textures that belong together, optionally creates render-ready
`.tx` files, creates one material subnetwork per texture set, and connects every
recognized map to the appropriate shader input. It supports USD MaterialX,
Karma, Arnold and MoonRay materials.

## Quick start

1. In Houdini, go to `/stage`.
2. Press Tab and create **Automated Texture Builder**.
3. Choose a **Texture Workflow** and select the **Texture Folder**.
4. Choose the material builder and surface model you want.
5. Choose **Automatic / UDIM** or **Repeating Tiled Image**.
6. Click **Convert, Build and Assign**.

The tool creates a visible Material Library LOP beside the controller. Inside
it, every detected texture set receives its own material-builder subnetwork.
The materials are not hidden inside the HDA.

Automatic mesh assignment is off by default. You can enable it when the texture
set names and USD mesh names are related.

## What the tool handles automatically

- Multiple materials and meshes in one texture folder
- Nested asset folders such as `textures/sculpt` and `textures/room`
- UDIM tiles using `1001`, `1002`, and similar filename tokens
- Base color, metalness, roughness, specular weight and normal maps
- Height and displacement
- Anisotropy and anisotropy angle
- Transmission, translucency and subsurface scattering
- Fuzz or sheen
- Coat, coat normal and coat tangent
- Thin film, opacity and emission
- Correct UV connections for every image
- OCIO color conversion without double-transforming generated TX files
- Source-aware texture precision for 8-bit, 16-bit, half and float images

The OpenPBR workflow recognizes the practical OpenPBR 1.1 texture set. It also
understands common aliases such as `Albedo`, `Metallic`, `Metalness`,
`Roughness`, `Sheen`, `Translucency`, and Painter's longer OpenPBR names.

## Texture workflows

### Use Source Images Directly

Uses the original EXR, TIFF, PNG or JPEG files. No TX files are created. This is
useful for testing or when another system already manages texture conversion.

### Generate / Update TX Files

Creates a `tx` folder beside the source textures and builds tiled, mipmapped TX
files. Normal operation is incremental: only missing, outdated, or incorrectly
stored TX files are rebuilt.

Enable **Regenerate All TX Files** when you deliberately want to replace every
generated TX file.

### Use Existing TX Files

Uses a folder of TX files without running maketx. You may select the TX folder
itself or its parent; the tool automatically finds a conventional `tx`
subfolder.

## Material choices

### Material builder

- **USD MaterialX Builder** — portable USD MaterialX material
- **Karma Material Builder** — Karma-focused MaterialX material
- **USD MaterialX Builder (Arnold)** — Arnold USD MaterialX material
- **Arnold Material Builder** — native Arnold Standard Surface network
- **MoonRay DwaBase** — native MoonRay material network

### Surface model

- **OpenPBR Surface** — recommended for Painter 12.1 OpenPBR projects and the
  most complete OpenPBR parameter mapping
- **MaterialX Standard Surface** — useful for established Standard Surface
  pipelines

OpenPBR MaterialX is the most faithful destination for the complete OpenPBR
parameter set. Arnold Standard Surface and MoonRay DwaBase receive the closest
supported equivalents where their native shader models differ.

## Texture naming and multiple materials

The name before the channel identifies the material or texture set. For
example:

```text
helmet_BaseColor.1001.exr
helmet_Roughness.1001.exr
helmet_Normal.1001.exr
helmet_TransmissionColor.1001.exr

cloth_BaseColor.1001.exr
cloth_Roughness.1001.exr
cloth_FuzzWeight.1001.exr
```

This produces separate `helmet` and `cloth` material subnetworks. Files may be
spread across subfolders; scanning is recursive and generated TX files preserve
the relative folder layout.

The bundled Substance Painter preset produces compatible names automatically.

## UV and tiling modes

- **Automatic / UDIM** uses ordinary MaterialX Image nodes and replaces
  detected tile numbers with `<UDIM>`.
- **Repeating Tiled Image** uses a shared MtlX USD Transform 2D node for scale,
  rotation and translation, then feeds regular MaterialX Image nodes with
  periodic wrapping.

Every MaterialX image receives an explicit UV connection. The default USD UV
primvar is `st`.

## Color management

Artists should normally leave **Use Current Houdini OCIO** enabled.

The tool reads the active OCIO configuration and its `scene_linear` role. Color
textures are converted to that scene-linear space when TX files are generated.
Data maps such as roughness, metalness, normal and displacement remain Raw.

### Height and displacement

Painter height pixels do not carry a dependable real-world displacement
distance. Connecting them to a displacement node at its default scale of 1 can
move points by one full scene unit and severely enlarge or break an asset.

The tool therefore authors two explicit controls:

- **Height / Displacement Scale** defaults to `0.01`. MaterialX and MoonRay use
  it in scene units; Native Arnold uses it as bump strength.
- **Height Zero Level** defaults to `0.0`, matching the signed floating-point
  height values preserved by the included Painter preset. Set it to `0.5` for
  a normalized height texture where middle gray is flat.

The MaterialX graph subtracts the zero level before MtlX Displacement applies
the scale. MoonRay receives the equivalent `zero_value` and
`height_multiplier` settings. These values remain artist controls because
texture pixels alone cannot determine the intended physical displacement.
Generated TX files are also read as Raw because their color conversion is
already baked in; this prevents a second transform.

The **TX Rule Check** should report that `.tx` resolves to Raw. If it shows a
warning, fix the TX file rule in the OCIO configuration before converting
textures.

## Texture precision

The artist does not need to choose a bit depth. The tool reads the actual pixel
type through OpenImageIO and applies this policy:

| Source and map type | Generated TX storage |
| --- | --- |
| 8-bit color texture | OCIO-converted half-float |
| 16-bit color texture | OCIO-converted float32 |
| 8/16-bit Raw data map | Preserved as 8/16-bit |
| Half/float Raw map | Preserved as half/float |
| Height or displacement | Float32 |

Promoting an 8-bit color image to half-float does not create missing detail. It
preserves the fractional values produced by the OCIO conversion and avoids
quantizing the linearized image back to 8-bit.

The detected source type and selected output type are recorded in the manifest
and in the generated TX metadata.

## Automatic USD assignment

Automatic assignment is optional and disabled by default.

When enabled, the tool first compares complete meaningful texture-set and USD
primitive names, including numeric suffixes such as `_14` and `_copy2`. It then
tries meaningful partial matches from the longest name to the shortest, helping
avoid assignments such as `Extract1` incorrectly matching `Extract12`. Imported
prefixes such as `bake_lp` and `shop_materialpath` are ignored. When Solaris
contains both a parent Mesh and its material GeomSubset, the GeomSubset is
preferred so partition-level bindings are preserved. Ambiguous matches are
skipped rather than guessed.

Bindings are written into each material entry's **Assign to Geometry** and
**Geometry Path** fields in the generated Material Library LOP. The tool does
not create a separate Assign Material node.

Use the **USD Geometry Root** field to limit matching to a particular part of
the Solaris scene graph.

For assigned UDIM materials, the tool also checks the inherited USD `st`
primvar (with `uv` as a fallback) and reports if the mesh references a UDIM tile
that is absent from the texture set. Extra texture tiles are allowed because a
shared texture set can cover several sibling meshes.

## Substance Painter preset

The included preset is:

`presets/Automated Texture Builder - Rec2020 TX Pipeline.spexp`

It exports the common hero-material maps:

- BaseColor
- BaseMetalness
- SpecularWeight
- SpecularRoughness
- SpecularRoughnessAnisotropy
- OpenGL Normal
- Height

The six surface maps are 16-bit half-float OpenEXR. Height is 32-bit float
OpenEXR.

The Houdini tool is not limited to those seven outputs. If a Painter template
also exports transmission, translucency, subsurface, fuzz, coat, thin-film,
opacity, emission or other recognized OpenPBR maps, they are discovered and
connected automatically.

Ambient occlusion is intentionally not multiplied into Base Color. AO is not
an OpenPBR Surface input, and baking it into a path-traced material can apply
the lighting effect twice.

## Advanced and safety controls

- **Record OIIO Inspection** stores detailed before/after image information in
  the manifest. It is off by default because it can slow large builds.
- **Texture Color Status** summarizes the latest conversion and reports color
  and Raw-data texture counts.
- **Delete Original Input Textures** removes only source files that have one
  verified TX counterpart. It is disabled in Source Images Directly mode. This
  action is permanent, so keep the source files until the TX build is checked.

The generated `automated_texture_manifest.json` records texture sets, paths,
UDIM tiles, color spaces, source/output pixel types, conversion status and
optional OIIO inspection reports.

## Installation

Run the installer whenever the tool is moved or Houdini is upgraded:

```sh
python3 /Users/j7s/coding/automated-texture-builder/scripts/install.py
```

It installs the Houdini 22 package and the Substance Painter export preset for
the current user. Restart Houdini and Painter so they rescan the assets.

The Houdini package is installed at:

```text
~/Library/Preferences/houdini/22.0/packages/automated_texture_builder.json
```

## Command-line use

The same conversion system can be run through Houdini's Python environment:

```sh
hython -m automated_texture_builder.cli /project/textures --force
```
