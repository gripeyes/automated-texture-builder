from pathlib import Path
import json
import tempfile
import unittest

from automated_texture_builder.conversion import (
    COLOR_CHANNELS,
    delete_original_sources,
    delete_sources_for_existing_tx,
    maketx_output_type,
    maketx_storage_args,
    resolve_existing_tx_root,
)


class ConversionSafetyTests(unittest.TestCase):
    def test_openpbr_color_and_data_channels_are_distinct(self):
        self.assertIn("translucency_color", COLOR_CHANNELS)
        self.assertIn("emission_color", COLOR_CHANNELS)
        self.assertNotIn("subsurface_radius_scale", COLOR_CHANNELS)
        self.assertNotIn("coat_normal", COLOR_CHANNELS)

    def test_maketx_uses_float_for_every_height_source(self):
        self.assertEqual(
            maketx_storage_args("height", Path("hero_Height.png"), "uint8"),
            ["--format", "exr", "-d", "float"],
        )
        self.assertEqual(maketx_output_type("height", "half"), "float")

    def test_eight_bit_color_is_safely_promoted_for_ocio(self):
        self.assertEqual(
            maketx_storage_args("base_color", Path("hero_BaseColor.jpg"), "uint8"),
            ["--format", "exr", "-d", "half"],
        )

    def test_sixteen_bit_color_uses_float_for_ocio(self):
        self.assertEqual(
            maketx_storage_args("base_color", Path("hero_BaseColor.tif"), "uint16"),
            ["--format", "exr", "-d", "float"],
        )

    def test_raw_maps_preserve_integer_storage(self):
        self.assertEqual(
            maketx_storage_args("specular_roughness", Path("hero_Roughness.png"), "uint8"),
            ["--format", "tiff", "-d", "uint8"],
        )
        self.assertEqual(
            maketx_storage_args("normal", Path("hero_Normal.tif"), "uint16"),
            ["--format", "tiff", "-d", "uint16"],
        )

    def test_raw_float_maps_preserve_float_class(self):
        self.assertEqual(
            maketx_storage_args("specular_roughness", Path("hero_Roughness.exr"), "half"),
            ["--format", "exr", "-d", "half"],
        )
        self.assertEqual(
            maketx_storage_args("specular_roughness", Path("hero_Roughness.exr"), "float"),
            ["--format", "exr", "-d", "float"],
        )

    def test_existing_tx_accepts_parent_or_tx_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            tx = source / "tx"
            tx.mkdir()
            (tx / "asset_BaseColor.tx").touch()
            self.assertEqual(resolve_existing_tx_root(source), tx.resolve())
            self.assertEqual(resolve_existing_tx_root(tx), tx.resolve())

    def test_delete_sources_requires_existing_generated_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory).resolve()
            tx_root = source_root / "tx"
            tx_root.mkdir()
            source = source_root / "asset_BaseColor.png"
            output = tx_root / "asset_BaseColor.tx"
            source.touch()
            output.touch()
            manifest = tx_root / "automated_texture_manifest.json"
            manifest.write_text(json.dumps({
                "source_root": str(source_root),
                "output_root": str(tx_root),
                "textures": [{"source": str(source), "output": str(output)}],
            }), encoding="utf-8")
            deleted = delete_original_sources(manifest)
            self.assertEqual(deleted, [source])
            self.assertFalse(source.exists())
            self.assertTrue(output.exists())

    def test_delete_sources_is_blocked_when_tx_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory).resolve()
            tx_root = source_root / "tx"
            tx_root.mkdir()
            source = source_root / "asset_BaseColor.png"
            source.touch()
            manifest = tx_root / "automated_texture_manifest.json"
            manifest.write_text(json.dumps({
                "source_root": str(source_root),
                "output_root": str(tx_root),
                "textures": [{
                    "source": str(source),
                    "output": str(tx_root / "asset_BaseColor.tx"),
                }],
            }), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                delete_original_sources(manifest)
            self.assertTrue(source.exists())

    def test_existing_tx_mode_deletes_only_source_with_matching_tx(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory).resolve()
            tx_root = source_root / "tx"
            tx_root.mkdir()
            source = source_root / "Extract12_BaseColor.png"
            output = tx_root / "Extract12_BaseColor.tx"
            source.touch()
            output.touch()
            deleted = delete_sources_for_existing_tx(source_root)
            self.assertEqual(deleted, [source])
            self.assertFalse(source.exists())
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
