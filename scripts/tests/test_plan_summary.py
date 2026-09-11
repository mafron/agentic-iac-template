import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from plan_summary import summarize  # noqa: E402


def resource(kind, actions, after=None, **extra):
    return {"address": f"{kind}.example", "type": kind, "mode": "managed",
            "change": {"actions": actions, "before": None, "after": after, "after_unknown": {}}, **extra}


def plan(*changes):
    return {"format_version": "1.2", "terraform_version": "1.16.2", "complete": True,
            "errored": False, "planned_values": {}, "resource_changes": list(changes)}


class PlanSummaryTests(unittest.TestCase):
    def reasons(self, rc):
        return summarize(plan(rc), "dev")["findings"][0]["reasons"]

    def test_replacements_are_exclusive_in_both_orders(self):
        p = plan(resource("aws_s3_bucket", ["create"], {}), resource("aws_s3_bucket", ["update"], {}),
                 resource("aws_s3_bucket", ["delete"]), resource("aws_s3_bucket", ["create", "delete"], {}),
                 resource("aws_s3_bucket", ["delete", "create"], {}), resource("aws_s3_bucket", ["no-op"], {}),
                 resource("aws_caller_identity", ["read"], {}, mode="data"))
        self.assertEqual(summarize(p, "dev")["counts"], {"create": 1, "update": 1, "delete": 1, "replace": 2})

    def test_noop_without_resource_changes(self):
        p = plan()
        del p["resource_changes"]
        self.assertEqual(summarize(p, "prod")["findings"], [])

    def test_iam_and_network_are_high_risk_on_creation(self):
        self.assertIn("IAM_CHANGE", self.reasons(resource("aws_iam_policy", ["create"], {})))
        self.assertIn("NETWORK_CHANGE", self.reasons(resource("aws_subnet", ["create"], {})))
        self.assertIn("SECURITY_GROUP_CHANGE", self.reasons(resource("aws_vpc_security_group_ingress_rule", ["update"], {})))

    def test_ipv6_and_before_exposure_are_reported(self):
        rc = resource("aws_security_group", ["update"], {"ingress": []})
        rc["change"]["before"] = {"ingress": [{"ipv6_cidr_blocks": ["::/0"]}]}
        self.assertIn("PUBLIC_CIDR_REVIEW", self.reasons(rc))

    def test_unknown_ids_are_ok_unknown_policy_is_not(self):
        rc = resource("aws_s3_bucket", ["create"], {})
        rc["change"]["after_unknown"] = {"id": True}
        self.assertEqual(summarize(plan(rc), "dev")["findings"], [])
        rc["change"]["after_unknown"] = {"policy": True}
        self.assertIn("UNKNOWN_SECURITY_VALUE", self.reasons(rc))

    def test_every_prod_change_requires_human_review(self):
        rc = resource("aws_s3_bucket", ["update"], {})
        self.assertIn("PRODUCTION", summarize(plan(rc), "prod")["findings"][0]["reasons"])

    def test_import_move_and_forget_are_state_operations(self):
        imported = resource("aws_s3_bucket", ["no-op"], {})
        imported["change"]["importing"] = {"id": "example"}
        moved = resource("aws_s3_bucket", ["no-op"], {}, previous_address="aws_s3_bucket.old")
        forgotten = resource("aws_s3_bucket", ["forget"])
        for rc in (imported, moved, forgotten):
            with self.subTest(rc=rc):
                self.assertIn("STATE_OPERATION", self.reasons(rc))

    def test_rejects_bad_incomplete_errored_and_state_json(self):
        bad_inputs = [None, {}, {"format_version": "1.0", "values": {}},
                      {**plan(), "complete": False}, {**plan(), "errored": True},
                      {**plan(), "format_version": "2.0"}, {**plan(), "resource_changes": None},
                      plan(resource("aws_s3_bucket", ["unexpected"], {})), plan({"change": {}})]
        for p in bad_inputs:
            with self.subTest(plan=p), self.assertRaises(ValueError):
                summarize(p, "prod")

    def test_stable_order_and_no_attribute_values_in_summary(self):
        rc = resource("aws_iam_policy", ["create"], {"policy": "sensitive-value-do-not-print"})
        p = plan(rc, resource("aws_security_group", ["create"], {}))
        reverse = copy.deepcopy(p)
        reverse["resource_changes"].reverse()
        result = summarize(p, "dev")
        self.assertEqual(result, summarize(reverse, "dev"))
        self.assertNotIn("sensitive-value-do-not-print", json.dumps(result))

    def test_cli_exit_statuses_and_fixtures(self):
        fixtures = SCRIPTS.parent / "fixtures" / "plans"
        for name, code in [("safe", 0), ("unsafe", 2)]:
            p = subprocess.run([sys.executable, str(SCRIPTS / "plan_summary.py"), str(fixtures / f"{name}.json"),
                                "--environment", "dev", "--fail-on-high-risk"], capture_output=True, text=True)
            self.assertEqual(p.returncode, code, p.stderr)
        p = subprocess.run([sys.executable, str(SCRIPTS / "plan_summary.py"), str(fixtures / "missing.json"),
                            "--environment", "prod"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)


if __name__ == "__main__":
    unittest.main()
