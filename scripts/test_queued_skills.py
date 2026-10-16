"""Client skills must poll the accepted job before using original results."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
QUEUED = (
    "inspect", "security", "review", "describe", "ask",
    "implement", "check-task", "explain", "review-arch", "control-flow", "slop-score",
)


def skill(name):
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def queued_contract(source):
    return source.split("## Queued Result\n\n", 1)[1].split("\n## ", 1)[0].strip()


class QueuedSkillsTests(unittest.TestCase):
    def test_create_issue_returns_direct_results_without_polling(self):
        source = skill("create-issue")
        self.assertNotIn("## Queued Result", source)
        self.assertIn("returns ticket results directly", source)
        self.assertIn("Do not poll for ticket creation", source)

    def test_every_queued_skill_allows_polling_and_keeps_original_result(self):
        for name in QUEUED:
            with self.subTest(skill=name):
                source = skill(name)
                tools_line = next(line for line in source.splitlines() if line.startswith("allowed-tools:"))
                allowed = json.loads(tools_line.partition(":")[2].strip())
                self.assertIn("mcp__plugin_cloudaeye_cloudaeye__get_job_result", allowed)
                self.assertIn("mcp__cloudaeye__get_job_result", allowed)
                self.assertIn("every 30 seconds", source)
                for status in ("queued", "running", "retrying", "completed", "failed", "error"):
                    self.assertIn(status, source)
                self.assertIn("expired", source)
                self.assertIn("inner `result` dictionary", source)

    def test_all_queued_tools_share_the_complete_rollout_and_timeout_contract(self):
        expected = queued_contract(skill("inspect"))
        for name in QUEUED:
            with self.subTest(skill=name):
                self.assertEqual(queued_contract(skill(name)), expected)
        for rule in (
            "initial response without a `job_id` whose `status` is not\n"
            "`queued`, `running`, or `retrying` is synchronous: use that response directly",
            "An initial `status: error` is a refusal,\nnot successful fallback; report it and stop.",
            "An active queued response without a non-empty `job_id` is malformed; stop.",
            "for at most 60 polling\ncalls and a 30-minute wall-clock deadline from submission, whichever comes\nfirst.",
            "Check the deadline before each call.",
            "preserve that ID to resume\nlater.",
            "Do not begin dependent actions or enqueue replacement work on timeout.",
            "require an inner `result` dictionary",
            "If a saved result expired or is\nmissing, say so, never call it empty/clean",
            "Poll using the submitting OAuth account.",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, expected)

    def test_card_skills_delegate_to_the_bounded_contract_instead_of_a_second_poll_loop(self):
        for name in ("review-arch", "control-flow", "slop-score"):
            with self.subTest(skill=name):
                source = skill(name)
                self.assertIn("Resolve the response using **Queued Result** above", source)
                self.assertEqual(source.count("every 30 seconds"), 1)

    def test_review_profiles_and_original_fields_are_not_replaced_by_cards(self):
        for name in ("inspect", "security", "review"):
            self.assertIn('`profile`: `"' + name + '"`', skill(name))
            self.assertIn("never renumber", skill(name))
        for name, field in (("describe", "description"), ("ask", "answer"), ("check-task", "report")):
            self.assertIn("`" + field + "` field", skill(name))

    def test_dependent_actions_wait_and_ticket_uncertainty_is_not_retried(self):
        for name in ("implement", "create-issue"):
            self.assertIn("existing job ID", skill(name))
            self.assertIn("saved report", skill(name))
        tickets = skill("create-issue")
        self.assertIn("explicit user approval", tickets)
        self.assertIn("unconfirmed delivery", tickets)
        self.assertIn("do not repeat the request automatically", tickets)
        self.assertNotIn("Re-running is safe", tickets)

    def test_queued_explain_never_resubmits_for_backend_progress(self):
        source = skill("explain")
        self.assertIn("deprecated", source)
        self.assertIn("same delegated CloudAEye analysis until terminal", " ".join(source.split()))
        self.assertNotIn("then call `explain` again", source)
        self.assertIn("never\n   call `explain` to advance a queued job", source)

    def test_explain_legacy_pending_resume_does_not_apply_to_nested_pending(self):
        source = skill("explain")
        legacy = source.split("## Legacy Explain Pending\n\n", 1)[1].split("\n## ", 1)[0]
        for rule in (
            "initial direct response has\n`status: pending` and no `job_id`",
            "same `issue`, `repo`, `source`, and any originally supplied `wait_seconds`",
            "at most three additional calls",
            "original 30-minute wall-clock deadline before every resume",
            "do not invent or ask for an MCP job ID",
            "An inner `status: pending` under outer `status: completed` is never this legacy",
            "do not re-submit `explain` or apply the three-call legacy resume allowance",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, legacy)
        self.assertIn("`pending`, direct legacy response without a job ID", source)
        self.assertIn("`pending`, nested under a completed queued result", source)


if __name__ == "__main__":
    unittest.main()
