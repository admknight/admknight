import importlib.util
import pathlib
import unittest

SRC = pathlib.Path(__file__).parents[1] / "tools" / "account_actions_monitor.py"
spec = importlib.util.spec_from_file_location("monitor", SRC)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def run(status, conclusion, created_at, url):
    return {"status": status, "conclusion": conclusion, "created_at": created_at, "html_url": url}


class MonitorTests(unittest.TestCase):
    def test_failure_not_hidden_by_other_repo_success(self):
        repo_list = [
            {"full_name": "admknight/a", "owner": {"login": "admknight"}, "private": False},
            {"full_name": "admknight/b", "owner": {"login": "admknight"}, "private": False},
            {"full_name": "admknight/private", "owner": {"login": "admknight"}, "private": True},
        ]
        def api(path):
            if path.startswith("/users/"):
                return repo_list
            if "/actions/workflows?" in path:
                return {"workflows": [{"id": 1, "name": "Tests", "state": "active", "path": ".github/workflows/test.yml"}]}
            if "/a/actions/workflows/1/runs" in path:
                return {"workflow_runs": [run("completed", "failure", "2026-10-08T01:00:00Z", "https://github.com/a/run")]}
            return {"workflow_runs": [run("completed", "success", "2026-10-09T01:00:00Z", "https://github.com/b/run")]}
        result = monitor.scan("admknight", api)
        badge, latest, details = monitor.render(result, "2026-10-09 01:10")
        self.assertEqual(result["repos"], 2)
        self.assertEqual(badge["message"], "1 failing")
        self.assertEqual(badge["color"], "critical")
        self.assertIn("b: success", latest["message"])
        self.assertIn("[Investigate](https://github.com/a/run)", details)

    def test_running_after_failure_still_warns(self):
        runs = [
            run("in_progress", None, "2026-10-09T01:01:00Z", "https://github.com/new"),
            run("completed", "failure", "2026-10-09T00:00:00Z", "https://github.com/old"),
        ]
        self.assertEqual(monitor.last_meaningful_run(runs)["conclusion"], "failure")
        self.assertEqual(monitor.last_meaningful_run([run("completed", "cancelled", "", ""), runs[1]])["conclusion"], "failure")

    def test_monitor_itself_excluded(self):
        def api(path):
            if path.startswith("/users/"):
                return [{"full_name": "admknight/admknight", "owner": {"login": "admknight"}, "private": False}]
            if "/actions/workflows?" in path:
                return {"workflows": [
                    {"id": 100, "name": "Monitor", "state": "active", "path": ".github/workflows/account-actions-monitor.yml"},
                    {"id": 101, "name": "Other", "state": "active", "path": ".github/workflows/chart.yml"},
                ]}
            return {"workflow_runs": [run("completed", "success", "2026-10-09T00:00:00Z", "https://github.com/chart")]}
        result = monitor.scan("admknight", api)
        self.assertEqual(len(result["workflows"]), 1)
        self.assertEqual(result["workflows"][0]["workflow"], "Other")

    def test_incomplete_scan_never_green(self):
        def error(_):
            raise RuntimeError("rate limit")
        result = monitor.scan("admknight", error)
        badge, latest, details = monitor.render(result, "2026-10-09 00:00")
        self.assertEqual(badge["color"], "orange")
        self.assertIn("1 unchecked", badge["message"])
        self.assertIn("Repository discovery", details)

    def test_profile_visits_only_fetch_once_per_utc_day(self):
        import tempfile
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile-visits.json"
            calls = []
            def fetch():
                calls.append(1)
                return "22"
            a = monitor.update_profile_visits(path, "2026-10-09", fetch)
            self.assertEqual(a["value"], "22")
            path.write_text(json.dumps(a), encoding="utf-8")
            b = monitor.update_profile_visits(path, "2026-10-09", fetch)
            self.assertEqual(b["value"], "22")
            self.assertEqual(len(calls), 1)
            c = monitor.update_profile_visits(path, "2026-10-10", lambda: "23")
            self.assertEqual(c["value"], "23")

    def test_profile_visits_api_failure_keeps_previous_count(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "visits.json"
            path.write_text('{"value":"22","lastAttemptUTC":"2026-10-08"}', encoding="utf-8")
            def unavailable():
                raise RuntimeError("bad connection")
            result = monitor.update_profile_visits(path, "2026-10-09", unavailable)
            self.assertEqual(result["value"], "22")
            self.assertFalse(monitor.VALID_VISITS.fullmatch("<script>"))

    def test_markdown_metadata_escaping(self):
        self.assertEqual(monitor.md("A|B\n<script>"), "A\\|B &lt;script&gt;")


if __name__ == "__main__":
    unittest.main()
