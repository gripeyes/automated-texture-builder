from pathlib import Path
import os
import unittest

from automated_texture_builder.conversion import load_ocio, scene_linear_space


class OcioTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("OCIO"), "$OCIO is not set")
    def test_scene_linear_comes_from_config_role(self):
        config = load_ocio(Path(os.environ["OCIO"]))
        expected = config.getRoleColorSpace("scene_linear")
        self.assertEqual(scene_linear_space(config), expected)


if __name__ == "__main__":
    unittest.main()
