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
5. Choose the UV, tiled, or triplanar texture mode you need.
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
Downloaded texture libraries that use a plain `_Color` suffix are treated as
Base Color as well. Common abbreviated library conventions are recognized at
token boundaries, including `Diff`/`Diffuse`, `Rough`/`Rgh`, `Metal`/`Met`,
`Nor_GL`/`Nrm_OpenGL`, `Disp`/`Displ`, and `Hgt`. Resolution suffixes such as
`1K`, `4K`, `8K`, and `16K` do not become part of the material name.

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
- **Tiled Texture with Hex Pattern Breakup** uses the shared USD Transform 2D
  plus MaterialX 1.39 Hex Tiled Image nodes. Normal textures use the dedicated
  Hex Tiled Normal Map node, while scalar maps take the red channel from the
  same randomized lookup. A single visible `texture_controls` node drives the
  tiling, rotation, scale, offset, falloff and contrast of every lookup in the
  material. This mode is available for the MaterialX builder
  profiles. Native Arnold and MoonRay do not expose an equivalent portable hex
  lookup here, so the tool rejects that combination with a clear message.
- **Triplanar Projection** projects textures in object space without requiring
  usable mesh UVs. Generic, Karma and Arnold USD profiles all use the same
  standard MtlX Triplanar Projection graph.
- **Triplanar with Pattern Breakup** adds a shared standard-MaterialX position
  variation before those projections to hide obvious repetition. The visible
  `texture_controls` node drives projection scale, blend, breakup frequency and
  breakup amount for every map together. The graph contains no Karma-specific
  shader nodes. Normal textures request the triplanar node's `vector3` signature
  directly, with no MtlX Convert, before the standard MtlX Normal Map decoding;
  the projection's normal input remains at its portable `Nobject` default.
  Generic MaterialX, Karma, Arnold USD MaterialX and native Arnold are
  supported. MoonRay is rejected because its Houdini integration has no
  compatible triplanar node.

UV-based MaterialX images receive an explicit UV connection. Triplanar modes
use object-space position and the projection node's standard `Nobject` default,
so they do not depend on `st`.

Enable **Offset Texture Per Instance** when repeated assets should not show the
same texture placement. Author a stable `vector3` USD primvar named
`atb_instance_offset` on each instance (or change **Instance Offset Primvar** to
your pipeline's name). Repeating and Hex modes add its XY components after the
shared USD Transform 2D; Triplanar modes add XYZ to object-space projection
coordinates. Missing primvars default to `(0, 0, 0)`, so non-instanced geometry
keeps its existing look. The generated `texture_controls` node exposes one
shared offset multiplier for all supported material builders. Keep the primvar
stable across frames to avoid texture swimming.

## Color management

Artists should normally leave **Use Current Houdini OCIO** enabled.

The tool reads the active OCIO configuration and its `scene_linear` role. Color
textures are converted to that scene-linear space when TX files are generated.
Data maps such as roughness, metalness, normal and displacement remain Raw.

PNG and JPEG color textures should normally stay on this conversion path.
Downloaded albedo/base-color images and ordinary Substance color exports are
usually sRGB-encoded, so their encoding must be decoded before lighting math.
The tool asks OCIO to classify every full file path, then converts from that
detected source space to the config's `scene_linear` role. Specific filename or
folder tags therefore override generic extension rules; for example, the
bundled configs recognize tags such as `_ACEScg_`, `_lin_rec709_`, `_Raw_`, and
`_sRGB_`.

**Skip PNG/JPEG Color Linearization** is an advanced escape hatch and is off by
default. Enabling it preserves PNG/JPEG color-map pixel values only when OCIO
classified them as display-referred, and stores their TX files as Raw without
an OCIO transform. An explicit filename/path rule identifying a linear or log
source still wins, so any required gamut or transfer conversion is preserved.
The option never affects roughness, metalness, normals, height, or other data
maps. Use it only when the pixels are already scene-linear in the project
working space but the files cannot be renamed or classified correctly. A
correct OCIO name/path rule remains preferable.

Generated TX filenames deliberately continue to mirror their source filenames,
which keeps UDIM grouping, incremental updates, source deletion checks, and
existing-TX discovery deterministic. Each TX is instead tagged internally with
its detected source color space, baked color space, Raw lookup space, channel,
and storage type. The JSON manifest records the same source/output information.
The OCIO `.tx` rule must remain first and Raw so these baked pixels are never
transformed a second time, regardless of tags in the original filename.

### Height and displacement

Substance Painter uses Height as its default displacement source. The tool
therefore connects Height to true displacement automatically. Painter's texture
export does not, however, embed a dependable scene-unit distance in the pixels;
connecting it at a renderer default scale of 1 can move points by one full scene
unit and severely enlarge or break an asset.

The tool uses map naming to choose the most specific available displacement
signal:

| Detected map | Automatic behavior |
| --- | --- |
| `Height` | Scalar true displacement along the normal |
| `Displacement` | Scalar true displacement along the normal |
| `VectorDisplacement` or `VDisp` | Three-channel true displacement |

Automatic selects exactly one signal in this order: vector displacement,
explicit scalar displacement, then height. It does not also apply the same
Height map as bump, avoiding duplicated detail. **Height / Displacement Mode**
can override this with Bump Only or Ignore.

The tool also authors separate bump and displacement controls because they use
different units:

- **Bump Scale** defaults to `1.0` and changes shading-normal strength without
  moving geometry.
- **Displacement Scale (Scene Units)** defaults to `0.01` and controls actual
  point movement for scalar and vector displacement.
- **Height Zero Level** defaults to `0.0`, matching the signed floating-point
  height values preserved by the included Painter preset. Set it to `0.5` for
  a normalized height texture where middle gray is flat.

For Bump Only, MaterialX chains MtlX Bump after the tangent normal map. For true
displacement, it subtracts the zero level before MtlX Displacement applies the
scale. Native Arnold and MoonRay create their corresponding safely scaled
scalar or vector displacement networks.

These values remain artist controls because texture pixels alone cannot
determine the intended physical displacement. True displacement also requires
renderer-side subdivision/dicing and displacement bounds.

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

Changing **Assign to Matching USD Meshes** or **USD Geometry Root** updates an
existing generated Material Library immediately; texture conversion does not
need to run again. The status field reports how many assignable USD prims were
found and warns clearly when none of the texture-set names match.

If downstream Solaris nodes were connected to the Automated Texture Builder
before the build, they are automatically rewired behind the generated Material
Library. This prevents the controller's pass-through output from bypassing the
materials and bindings.

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
