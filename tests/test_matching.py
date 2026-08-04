import unittest

from automated_texture_builder.matching import match_materials_to_paths


class MatchingTests(unittest.TestCase):
    def test_tallsculpt_names_all_match_unique_meshes(self):
        names = (
            "Extract12", "Extract51", "PolySphere6_14",
            "PolySphere6_14_copy1", "PolySphere6_14_copy2",
        )
        materials = {
            f"bake_lp_{name}": f"/materials/bake_lp_{name}"
            for name in names
        }
        candidates = [
            f"/sopcreate1/unwrapped/shop_materialpath_{name}"
            for name in names
        ]
        expected = {
            f"bake_lp_{name}": f"/sopcreate1/unwrapped/shop_materialpath_{name}"
            for name in names
        }
        self.assertEqual(match_materials_to_paths(materials, candidates), expected)

    def test_matching_geomsubset_wins_over_parent_mesh(self):
        materials = {"bake_lp_Extract12": "/materials/bake_lp_Extract12"}
        candidates = [
            ("/asset/Extract12", False),
            ("/asset/Extract12/shop_materialpath_Extract12", True),
        ]
        self.assertEqual(
            match_materials_to_paths(materials, candidates),
            {"bake_lp_Extract12": "/asset/Extract12/shop_materialpath_Extract12"},
        )

    def test_numbered_names_do_not_partially_cross_match(self):
        materials = {"asset_Extract1": "/materials/asset_Extract1"}
        candidates = ["/asset/Extract12"]
        self.assertEqual(match_materials_to_paths(materials, candidates), {})

    def test_ambiguous_partial_matches_are_skipped(self):
        materials = {"hero_helmet": "/materials/hero_helmet"}
        candidates = ["/asset/helmet_left", "/asset/helmet_right"]
        self.assertEqual(match_materials_to_paths(materials, candidates), {})


if __name__ == "__main__":
    unittest.main()
