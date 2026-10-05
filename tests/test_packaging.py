import tomllib
import unittest
from pathlib import Path

from simpleui_nodes.version import PACK_NAME, PACK_VERSION

ROOT = Path(__file__).resolve().parent.parent


class PackagingTests(unittest.TestCase):
    def test_pyproject_matches_version_constants(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["name"], PACK_NAME)
        self.assertEqual(project["version"], PACK_VERSION)
        self.assertEqual(project["dependencies"], [])


if __name__ == "__main__":
    unittest.main()
