import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LinterIntegrationTests(unittest.TestCase):
    def test_rules_linter_runs_without_errors(self) -> None:
        cmd = [
            sys.executable,
            str(ROOT / "src" / "rules_linter.py"),
            "--rules-data-dir",
            str(ROOT / "rules_data"),
            "--schema-dir",
            str(ROOT / "schemas"),
            "--encounter",
            str(ROOT / "examples"),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("errors=0", proc.stdout)


if __name__ == "__main__":
    unittest.main()
