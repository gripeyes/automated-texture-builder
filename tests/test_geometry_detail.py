import unittest

from automated_texture_builder.geometry_detail import geometry_detail_plan


class GeometryDetailTests(unittest.TestCase):
    def test_auto_keeps_height_as_bump(self):
        self.assertEqual(geometry_detail_plan({"height": {}}, "auto"), ("height", None))

    def test_auto_distinguishes_height_and_displacement(self):
        self.assertEqual(
            geometry_detail_plan({"height": {}, "displacement": {}}, "auto"),
            ("height", "displacement"),
        )

    def test_auto_prefers_vector_displacement(self):
        self.assertEqual(
            geometry_detail_plan(
                {"height": {}, "displacement": {}, "vector_displacement": {}}, "auto",
            ),
            ("height", "vector_displacement"),
        )

    def test_true_displacement_uses_height_as_last_fallback(self):
        self.assertEqual(
            geometry_detail_plan({"height": {}}, "displacement"),
            (None, "height"),
        )

    def test_off_disconnects_geometry_detail(self):
        self.assertEqual(
            geometry_detail_plan({"height": {}, "displacement": {}}, "off"),
            (None, None),
        )


if __name__ == "__main__":
    unittest.main()
