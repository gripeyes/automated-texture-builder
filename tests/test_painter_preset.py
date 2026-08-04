from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("preset", ROOT / "scripts" / "build_painter_preset.py")
PRESET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRESET)


class PainterPresetTests(unittest.TestCase):
    def test_installed_preset_channels(self):
        path = ROOT / "presets" / "Automated Texture Builder - Rec2020 TX Pipeline.spexp"
        data = path.read_bytes()
        for token in (
            b"_BaseColor(", b"_Metalness(", b"_Roughness(", b"_Normal(",
            b"_Height(", b"_SpecularWeight(", b"_Anisotropy(",
        ):
            self.assertIn(token, data)
        self.assertNotIn(b"_Emissive(", data)
        self.assertEqual(len(PRESET.segments(data)), 7)


if __name__ == "__main__":
    unittest.main()
