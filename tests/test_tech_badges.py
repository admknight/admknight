import importlib.util
import pathlib
import unittest
import xml.etree.ElementTree as ET

SCRIPT = pathlib.Path(__file__).parents[1] / "tools" / "build_tech_badges.py"
spec = importlib.util.spec_from_file_location("tech_badges", SCRIPT)
badges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(badges)


class TechArsenalTests(unittest.TestCase):
    def test_inventory_has_26_unique_technologies_and_original_four_categories(self):
        items = badges.TECHNOLOGIES
        self.assertEqual(len(items), 26)
        self.assertEqual(len({item[2] for item in items}), 26)
        self.assertEqual(tuple(dict.fromkeys(item[0] for item in items)), badges.CATEGORIES)
        self.assertEqual([sum(item[0] == category for item in items) for category in badges.CATEGORIES],
                         [8, 5, 6, 7])

    def test_badge_has_real_vector_logo_and_accessible_label(self):
        tech = badges.TECHNOLOGIES[0]
        example = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0h24v24z"/></svg>'
        paths = badges.paths_from_svg(example)
        svg = badges.badge_svg(tech, paths)
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib["aria-label"], "Python")
        self.assertTrue(any(child.tag.endswith("path") for child in root.iter()))
        self.assertIn('fill="#77BDF3"', svg)
        self.assertIn("stroke=\"#34536D\"", svg)
        self.assertNotIn("<script", svg)
        self.assertNotIn("<image", svg)
        self.assertNotIn("href=", svg)

    def test_untrusted_source_svg_cannot_inject_scripts_or_external_content(self):
        bad = b'<svg viewBox="0 0 24 24"><path d="M0 0\" onload=\"alert(1)\""/></svg>'
        with self.assertRaises(ValueError):
            badges.paths_from_svg(bad)
        with self.assertRaises(ValueError):
            badges.paths_from_svg(b'<svg viewBox="0 0 128 128"><path d="M0 0z"/></svg>')
        with self.assertRaises(ValueError):
            badges.paths_from_svg(b'<svg viewBox="0 0 24 24"><text>not a real logo</text></svg>')

    def test_source_snapshots_are_pinned(self):
        self.assertRegex(badges.SIMPLE_ICONS_REV, r"^[0-9a-f]{40}$")
        self.assertEqual(badges.LEGACY["css3"], "13.21.0")
        self.assertEqual(badges.LEGACY["visualstudiocode"], "11.0.0")
        self.assertEqual(badges.source_url("python").split("/")[-1], "python.svg")


if __name__ == "__main__":
    unittest.main()
