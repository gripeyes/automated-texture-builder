from pathlib import Path
import tempfile
import unittest

from automated_texture_builder.discovery import parse_texture, scan, udim_pattern


class DiscoveryTests(unittest.TestCase):
    def test_core_material_channels(self):
        cases = {
            "hero_helmet_BaseColor_Linear Rec.2020.1001.exr": "base_color",
            "hero_helmet_Metalness_Raw.1001.tif": "base_metalness",
            "hero_helmet_SpecularWeight_Raw.1001.tif": "specular_weight",
            "hero_helmet_Roughness_Raw.1001.tif": "specular_roughness",
            "hero_helmet_Anisotropy_Raw.1001.tif": "specular_roughness_anisotropy",
            "hero_helmet_Normal_OpenGL_Raw.1001.tif": "normal",
            "hero_helmet_Height_Raw.1001.exr": "height",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                texture = parse_texture(Path("/tmp") / name)
                self.assertIsNotNone(texture)
                self.assertEqual(texture.channel, expected)
                self.assertEqual(texture.udim, 1001)

    def test_scan_excludes_tx_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "asset_BaseColor.1001.exr").touch()
            (root / "tx").mkdir()
            (root / "tx" / "asset_Roughness.1001.tif").touch()
            result = scan(root, root / "tx")
            self.assertEqual(set(result["asset"].maps), {"base_color"})

    def test_scan_recurses_across_sibling_asset_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sculpt").mkdir()
            (root / "room").mkdir()
            (root / "sculpt" / "Extract12_BaseColor.png").touch()
            (root / "room" / "Wall_BaseColor.png").touch()
            result = scan(root, root / "tx")
            self.assertEqual(set(result), {"Extract12", "Wall"})

    def test_extended_material_channels(self):
        cases = {
            "hero_TransmissionColor_Linear Rec.2020.1001.exr": "transmission_color",
            "hero_BaseDiffuseRoughness_Raw.1001.exr": "base_diffuse_roughness",
            "hero_Transmission_Raw.1001.tif": "transmission_weight",
            "hero_TransmissionDispersionScale_Raw.1001.exr": "transmission_dispersion_scale",
            "hero_TransmissionDispersionAbbeNumber_Raw.1001.exr": "transmission_dispersion_abbe_number",
            "hero_Translucency_Raw.1001.exr": "translucency_weight",
            "hero_TranslucencyColor_Linear Rec.2020.1001.exr": "translucency_color",
            "hero_SubsurfaceColor_Linear Rec.2020.1001.exr": "subsurface_color",
            "hero_SubsurfaceRadius_Raw.1001.exr": "subsurface_radius",
            "hero_SubsurfaceRadiusScale_Raw.1001.exr": "subsurface_radius_scale",
            "hero_FuzzRoughness_Raw.1001.tif": "fuzz_roughness",
            "hero_CoatRoughness_Raw.1001.tif": "coat_roughness",
            "hero_CoatNormal_Raw.1001.exr": "coat_normal",
            "hero_CoatTangent_Raw.1001.exr": "coat_tangent",
            "hero_Tangent_Raw.1001.exr": "tangent",
            "hero_SpecularAnisotropy_Raw.1001.exr": "specular_roughness_anisotropy",
            "hero_CoatAnisotropy_Raw.1001.exr": "coat_roughness_anisotropy",
            "hero_AnisotropyAngle_Raw.1001.exr": "specular_anisotropy_angle",
            "hero_CoatAnisotropyAngle_Raw.1001.exr": "coat_anisotropy_angle",
            "hero_ThinFilmThickness_Raw.1001.exr": "thin_film_thickness",
            "hero_ThinWalled_Raw.1001.exr": "thin_walled",
            "hero_Opacity_Raw.1001.tif": "opacity",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(parse_texture(Path("/tmp") / name).channel, expected)

    def test_udim_pattern(self):
        texture = parse_texture(Path("/tmp/asset_Roughness.1002.tif"))
        self.assertTrue(udim_pattern([texture], use_output=False).endswith("/asset_Roughness.<UDIM>.tif"))

    def test_udim_pattern_never_rewrites_parent_folder(self):
        texture = parse_texture(Path("/tmp/1001/asset_Roughness.1002.tif"))
        self.assertTrue(
            udim_pattern([texture], use_output=False).endswith(
                "/1001/asset_Roughness.<UDIM>.tif"
            ),
        )


if __name__ == "__main__":
    unittest.main()
