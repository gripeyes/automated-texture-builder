from pathlib import Path
import json
import tempfile
import unittest

from automated_texture_builder.conversion import (
    delete_original_sources,
    delete_sources_for_existing_tx,
    resolve_existing_tx_root,
)


class ConversionSafetyTests(unittest.TestCase):
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
