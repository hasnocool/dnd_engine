import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliABTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(ROOT / "src" / "turn_engine.py"),
            str(ROOT / "examples" / "demo_encounter.json"),
            *args,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def _run_cli_json(self, *args: str) -> dict:
        completed = self._run_cli("--json", *args)
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"CLI failed with code {completed.returncode}: {completed.stderr}",
        )
        return json.loads(completed.stdout)

    def test_invalid_action_policy_exits_with_helpful_error(self) -> None:
        completed = self._run_cli("--action-policy", "nope")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("invalid choice", completed.stderr)
        self.assertIn("--action-policy", completed.stderr)

    def test_invalid_target_policy_exits_with_helpful_error(self) -> None:
        completed = self._run_cli("--target-policy", "nope")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("invalid choice", completed.stderr)
        self.assertIn("--target-policy", completed.stderr)

    def test_ab_json_has_expected_schema_keys(self) -> None:
        payload = self._run_cli_json(
            "--ab-action-policy",
            "best_damage",
            "--ab-target-policy",
            "lowest_ac",
            "--ab-runs",
            "2",
        )

        self.assertEqual(payload["ab_runs"], 2)
        self.assertIn("baseline", payload)
        self.assertIn("variant", payload)
        self.assertIn("runs", payload)

        baseline = payload["baseline"]
        variant = payload["variant"]
        self.assertEqual(set(baseline.keys()), {"target_policy", "action_policy", "wins"})
        self.assertEqual(set(variant.keys()), {"target_policy", "action_policy", "wins"})
        self.assertEqual(baseline["target_policy"], "lowest_hp")
        self.assertEqual(baseline["action_policy"], "first")
        self.assertEqual(variant["target_policy"], "lowest_ac")
        self.assertEqual(variant["action_policy"], "best_damage")

        runs = payload["runs"]
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertIn("seed", run)
            self.assertIn("baseline", run)
            self.assertIn("variant", run)
            self.assertEqual(
                set(run["baseline"].keys()),
                {"target_policy", "action_policy", "winner", "reason", "events"},
            )
            self.assertEqual(
                set(run["variant"].keys()),
                {"target_policy", "action_policy", "winner", "reason", "events"},
            )

    def test_ab_seed_stepping(self) -> None:
        payload = self._run_cli_json(
            "--ab-action-policy",
            "spell_first",
            "--ab-runs",
            "3",
            "--ab-seed-step",
            "7",
        )

        seeds = [run["seed"] for run in payload["runs"]]
        self.assertEqual(seeds, [1337, 1344, 1351])


if __name__ == "__main__":
    unittest.main()
