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

    def test_all_outputs_are_half_float_exr(self):
        path = ROOT / "presets" / "Automated Texture Builder - Rec2020 TX Pipeline.spexp"
        data = path.read_bytes()
        for start, end in PRESET.segments(data):
            output = data[start:end]
            self.assertIn(b"fileformat\x10\x03\x00\x00\x00exr", output)
            self.assertIn(b"bitdepth\x09\x02\x00\x00\x00\x00\x00\x00\x00", output)


if __name__ == "__main__":
    unittest.main()
