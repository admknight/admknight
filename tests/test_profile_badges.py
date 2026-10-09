import importlib.util
import pathlib
import unittest
import xml.etree.ElementTree as ET

SRC = pathlib.Path(__file__).parents[1] / "tools" / "profile_badges.py"
spec = importlib.util.spec_from_file_location("profile_badges", SRC)
badges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(badges)


class BadgeTests(unittest.TestCase):
    def test_failure_not_hidden_by_latest_success(self):
        data = {"repos": 23, "workflows": [{"failed": True}, {"failed": False}],
                "latest": {"repo": "admknight/second-repo", "conclusion": "success"},
                "unknown": []}
        svg = badges.actions_card(data, "2026-10-09 03:30")
        ET.fromstring(svg)
        self.assertIn("1 workflow needs attention", svg)
        self.assertIn(badges.RED, svg)
        self.assertIn("second-repo", svg)

    def test_success_and_incomplete_scan(self):
        data = {"repos": 2, "workflows": [{"failed": False}], "unknown": [],
                "latest": {"repo": "admknight/project", "conclusion": "success"}}
        self.assertIn("ALL CLEAR", badges.actions_card(data, "2026-10-09 00:00"))
        data["unknown"] = [("unreachable", "rate limited")]
        self.assertIn("PARTIAL COVERAGE", badges.actions_card(data, "2026-10-09 00:00"))

    def test_stats_metrics_are_unique(self):
        svg = badges.stats_strip(23, 4, 1, 0, 22)
        ET.fromstring(svg)
        for key in ("PUBLIC REPOS", "TOTAL STARS", "FOLLOWERS", "PUBLIC GISTS", "PROFILE VISITS"):
            self.assertEqual(svg.count(">" + key + "<"), 1)

    def test_profile_visits_are_a_single_real_numeric_column(self):
        svg = badges.stats_strip(23, 4, 1, 0, 28)
        ET.fromstring(svg)
        self.assertEqual(svg.count(">PROFILE VISITS<"), 1)
        self.assertIn(">28</text>", svg)

    def test_quick_links_valid_and_self_contained(self):
        for kind in ("portfolio", "builder"):
            svg = badges.quick_link(kind)
            ET.fromstring(svg)
            self.assertNotIn("<script", svg)
            self.assertNotIn("<image", svg)
            self.assertNotIn("<foreignObject", svg)

    def test_dynamic_values_are_xml_escaped(self):
        data = {"repos": 1, "workflows": [{"failed": False}], "unknown": [],
                "latest": {"repo": "admknight/test<&", "conclusion": "success"}}
        svg = badges.actions_card(data, "2026<test>")
        ET.fromstring(svg)
        self.assertIn("test&lt;&amp;", svg)
        self.assertIn("2026&lt;test&gt;", svg)


if __name__ == "__main__":
    unittest.main()
