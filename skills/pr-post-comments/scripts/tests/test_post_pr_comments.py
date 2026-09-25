"""Tests for post_pr_comments.py: parsing, voice lint, pacing, and what reaches gh."""

import importlib.util
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "post_pr_comments", Path(__file__).resolve().parents[1] / "post_pr_comments.py"
)
driver = importlib.util.module_from_spec(SPEC)
# dataclasses resolve string annotations through sys.modules on 3.9.
sys.modules[SPEC.name] = driver
SPEC.loader.exec_module(driver)


class FixedRandom(random.Random):
    """Every uniform() draw lands on the low or high end of its range."""

    def __init__(self, high: bool) -> None:
        super().__init__()
        self.high = high

    def uniform(self, a, b):
        return b if self.high else a


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now
        self.slept = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(round(seconds, 3))
        self.now += seconds


class TestLint(unittest.TestCase):
    def test_flags_each_hard_rule(self) -> None:
        cases = {
            "fine — mostly": "em or en dash",
            "So the cache is wrong.": "'So'",
            "the cache is wrong. Okay, fixed.": "'Okay'",
            "yeah that works": "'yeah'",
            "Furthermore it leaks.": "banned phrase",
            "In terms of latency it's fine.": "banned phrase",
            "I checked the base branch and it's there.": "banned phrase",
        }
        for body, expected in cases.items():
            with self.subTest(body):
                problems = driver.lint(body, needs_tag=False)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(expected, problems[0])

    def test_passes_real_replies_and_code_spans(self) -> None:
        bodies = [
            "yep, moved it onto the type, so the tool just hands it over.",
            "right, dispatch already refuses it. Well-known trap though.",
            "the `robust_parse` helper and ```So = 1 — x``` stay as they are",
            "also so, then, okay mid-sentence is fine",
        ]
        for body in bodies:
            with self.subTest(body):
                self.assertEqual(driver.lint(body, needs_tag=False), [])

    def test_inline_comments_need_a_tag(self) -> None:
        self.assertEqual(driver.lint("[o] rename it", needs_tag=True), [])
        self.assertEqual(len(driver.lint("rename it", needs_tag=True)), 1)


class TestParseEntries(unittest.TestCase):
    def test_builds_the_three_kinds_of_post(self) -> None:
        raw = [
            {"in_reply_to": 3992873113, "body": "done, renamed"},
            {"path": "app/a.py", "start_line": 9, "line": 12, "body": "[r] leaks the handle"},
            {"body": "one PR-level note"},
        ]
        comments, problems = driver.parse_entries("o/r", 7, raw, "abc123")
        self.assertEqual(problems, [])
        self.assertEqual(
            [(c.endpoint, c.payload) for c in comments],
            [
                ("repos/o/r/pulls/7/comments/3992873113/replies", {"body": "done, renamed"}),
                ("repos/o/r/pulls/7/comments", {
                    "commit_id": "abc123", "path": "app/a.py", "line": 12, "side": "RIGHT",
                    "body": "[r] leaks the handle", "start_line": 9, "start_side": "RIGHT"}),
                ("repos/o/r/issues/7/comments", {"body": "one PR-level note"}),
            ],
        )

    def test_reports_every_bad_entry(self) -> None:
        raw = [
            {"body": ""},
            {"in_reply_to": "abc", "body": "x"},
            {"path": "a.py", "line": 3, "body": "[o] x"},
            {"body": "So this is off — badly."},
        ]
        _comments, problems = driver.parse_entries("o/r", 7, raw, None)
        self.assertEqual(len(problems), 5, problems)
        self.assertEqual(
            [p.split(":")[0].split(" (")[0] for p in problems],
            ["entry 1", "entry 2", "entry 3", "entry 4", "entry 4"],
        )

    def test_refuses_an_empty_or_non_list_file(self) -> None:
        for raw in ([], {"body": "x"}):
            with self.subTest(raw):
                self.assertEqual(driver.parse_entries("o/r", 1, raw, None)[1], ["the file must hold a non-empty JSON list"])


class TestDelay(unittest.TestCase):
    def test_matches_the_skill_worked_examples(self) -> None:
        # pr-post-comments Step 6: a 120-char [o] waits 30-60 s.
        self.assertEqual(driver.delay_for(120, FixedRandom(high=False)), 15 + 15)
        self.assertEqual(driver.delay_for(120, FixedRandom(high=True)), 35 + 25)

    def test_caps_the_writing_time(self) -> None:
        self.assertEqual(driver.delay_for(100_000, FixedRandom(high=True)), 35 + 225)


class TestRun(unittest.TestCase):
    def setUp(self) -> None:
        self.state = Path(tempfile.mkdtemp()) / "last-post"
        self.posted = []

    def comments(self, *lengths):
        return [driver.Comment(f"c{i}", f"e{i}", {"body": "x" * n}, "x" * n) for i, n in enumerate(lengths, 1)]

    def post(self, comment):
        self.posted.append(comment.label)
        return f"https://github.com/x#{comment.label}"

    def test_first_post_is_immediate_and_each_next_waits_its_writing_time(self) -> None:
        clock = FakeClock(10_000.0)
        failures = driver.run(
            self.comments(120, 600), post=self.post, clock=clock, sleep=clock.sleep,
            rng=FixedRandom(high=False), last_post=self.state,
        )
        self.assertEqual(failures, [])
        self.assertEqual(self.posted, ["c1", "c2"])
        self.assertEqual(clock.slept, [15 + 75.0])
        self.assertEqual(float(self.state.read_text()), 10_090.0)

    def test_a_new_run_waits_on_the_last_post_of_the_previous_one(self) -> None:
        self.state.write_text("9990.0\n")
        clock = FakeClock(10_000.0)
        driver.run(self.comments(120), post=self.post, clock=clock, sleep=clock.sleep,
                   rng=FixedRandom(high=False), last_post=self.state)
        self.assertEqual(clock.slept, [20.0])

    def test_a_failed_post_is_reported_and_the_rest_still_go(self) -> None:
        def flaky(comment):
            if comment.label == "c1":
                raise driver.PostError("422")
            return self.post(comment)

        clock = FakeClock(10_000.0)
        failures = driver.run(self.comments(10, 10), post=flaky, clock=clock, sleep=clock.sleep,
                              rng=FixedRandom(high=False), last_post=self.state)
        self.assertEqual((failures, self.posted), (["c1"], ["c2"]))


class TestMain(unittest.TestCase):
    def test_a_lint_failure_posts_nothing(self) -> None:
        folder = Path(tempfile.mkdtemp())
        comments = folder / "c.json"
        comments.write_text(json.dumps([{"body": "fine"}, {"body": "So, no."}]))
        called = []
        original = driver.gh_post
        driver.gh_post = lambda comment: called.append(comment) or "url"
        try:
            self.assertEqual(driver.main(["o/r", "1", str(comments)]), 2)
        finally:
            driver.gh_post = original
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
