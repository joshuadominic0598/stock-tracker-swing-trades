import ast
import subprocess
import sys
import tempfile
import unittest

from swing_signal.paths import DATA_DIR, PROJECT_ROOT, WEB_ROOT
from tools.format_python import compact_sections

class ProjectLayoutTests(unittest.TestCase):
    def test_source_workspace_and_bundled_assets_keep_their_locations(self):
        self.assertEqual(DATA_DIR, PROJECT_ROOT / "data")
        for asset in ("index.html", "app.js", "charts.js", "vendor/lightweight-charts.js"):
            self.assertTrue((WEB_ROOT / asset).is_file(), asset)

    def test_source_launcher_works_outside_project_without_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "launch.py"), "--help"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
        self.assertIn("--data-dir", result.stdout)
        self.assertIn("--no-refresh", result.stdout)

    def test_blank_line_cleanup_preserves_multiline_string_values(self):
        source = 'message = """first\n\n\nlast"""\n\n\ndef read():\n    return message\n'
        compact = compact_sections(source)
        self.assertEqual(ast.dump(ast.parse(source)), ast.dump(ast.parse(compact)))
        self.assertIn("first\n\n\nlast", compact)
        self.assertIn('"""\n\ndef read', compact)

    def test_blank_line_cleanup_preserves_multiline_fstrings(self):
        source = 'value = 3\n\n\nmessage = f"""first {value}\n\n\nlast"""\n'
        compact = compact_sections(source)
        self.assertEqual(ast.dump(ast.parse(source)), ast.dump(ast.parse(compact)))
        self.assertIn("first {value}\n\n\nlast", compact)
        self.assertEqual(compact_sections(compact), compact)

if __name__ == "__main__":
    unittest.main()
