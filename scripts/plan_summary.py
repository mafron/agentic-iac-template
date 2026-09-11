#!/usr/bin/env python3
"""Review terraform show -json output without printing resource attribute values.

This is a deliberately conservative triage tool, not an authorization engine.
Replacement is one exclusive category; data reads do not count as creates.
"""
import argparse
import ipaddress
import json
import sys
from pathlib import Path

ACTION_KINDS = {
    ("create",): "create", ("update",): "update", ("delete",): "delete",
    ("delete", "create"): "replace", ("create", "delete"): "replace",
    ("no-op",): None, ("read",): None, ("forget",): "state",
    ("create", "forget"): "state",
}
NETWORK_PREFIXES = (
    "aws_vpc", "aws_subnet", "aws_security_group", "aws_route",
    "aws_network_acl", "aws_internet_gateway", "aws_nat_gateway",
    "aws_default_security_group", "aws_default_network_acl",
)
SECURITY_KEYS = {
    "policy", "assume_role_policy", "ingress", "egress", "cidr_block",
    "cidr_blocks", "ipv6_cidr_blocks", "cidr_ipv4", "cidr_ipv6", "ip_protocol",
    "from_port", "to_port", "acl", "block_public_acls", "block_public_policy",
    "ignore_public_acls", "restrict_public_buckets", "map_public_ip_on_launch",
    "publicly_accessible", "tags", "tags_all",
}


def leaves(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from leaves(child)
    else:
        yield value


def public_cidr(value):
    for item in leaves(value):
        if isinstance(item, str) and "/" in item:
            try:
                if ipaddress.ip_network(item, strict=False).prefixlen == 0:
                    return True
            except ValueError:
                pass
    return False


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("Expected a Terraform plan JSON object")
    if not str(plan.get("format_version", "")).startswith("1."):
        raise ValueError("Unsupported or missing plan format_version")
    if not isinstance(plan.get("terraform_version"), str) or not isinstance(plan.get("planned_values"), dict):
        raise ValueError("Expected plan metadata and planned_values; state JSON is not a plan")
    if plan.get("errored") is not False or plan.get("complete") is not True:
        raise ValueError("Errored, incomplete or unqualified plan cannot pass review")
    changes = plan.get("resource_changes", [])
    if not isinstance(changes, list):
        raise ValueError("resource_changes must be an array")
    for rc in changes:
        if not isinstance(rc, dict) or not all(isinstance(rc.get(k), str) for k in ("address", "type", "mode")):
            raise ValueError("Malformed resource change identity")
        if rc["mode"] not in ("managed", "data") or not isinstance(rc.get("change"), dict):
            raise ValueError("Malformed resource change mode/body")
        change = rc["change"]
        actions = change.get("actions")
        if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions) or tuple(actions) not in ACTION_KINDS:
            raise ValueError("Unsupported action sequence; update the harness before continuing")
        for key in ("before", "after"):
            if change.get(key) is not None and not isinstance(change[key], dict):
                raise ValueError(f"{key} must be an object or null")
        unknown = change.get("after_unknown", {})
        if not isinstance(unknown, dict) and unknown is not True and unknown is not False:
            raise ValueError("after_unknown must be an object or boolean")
    return changes


def summarize(plan, environment):
    if environment not in ("dev", "staging", "prod"):
        raise ValueError("Environment must come from the trusted caller")
    changes = validate_plan(plan)
    counts = dict.fromkeys(("create", "update", "delete", "replace"), 0)
    findings = []
    for rc in changes:
        if rc["mode"] != "managed":
            continue
        change, resource_type = rc["change"], rc["type"]
        kind = ACTION_KINDS[tuple(change["actions"])]
        state_operation = bool(rc.get("previous_address")) or "importing" in change or kind == "state"
        if kind is None and not state_operation:
            continue
        if kind in counts:
            counts[kind] += 1
        reasons = set()
        if environment == "prod":
            reasons.add("PRODUCTION")
        if state_operation:
            reasons.add("STATE_OPERATION")
        if kind in ("delete", "replace"):
            reasons.add("DELETION")
        if kind == "replace":
            reasons.add("REPLACEMENT")
        if resource_type.startswith("aws_iam_"):
            reasons.add("IAM_CHANGE")
        if resource_type.startswith(NETWORK_PREFIXES):
            reasons.add("NETWORK_CHANGE")
        if "security_group" in resource_type:
            reasons.add("SECURITY_GROUP_CHANGE")
        if resource_type.startswith(("aws_kms_", "aws_db_", "aws_rds_")):
            reasons.add("KMS_OR_DATABASE_CHANGE")
        before, after = change.get("before") or {}, change.get("after") or {}
        if public_cidr(before) or public_cidr(after):
            reasons.add("PUBLIC_CIDR_REVIEW")
        if resource_type in ("aws_s3_bucket_policy", "aws_s3_bucket_acl", "aws_s3_bucket_public_access_block"):
            reasons.add("PUBLIC_ACCESS_CONTROL_CHANGE")
        if after.get("publicly_accessible") is True or after.get("map_public_ip_on_launch") is True:
            reasons.add("PUBLIC_EXPOSURE")
        unknown = change.get("after_unknown", {})
        if unknown is True or (isinstance(unknown, dict) and any(
            any(v is True for v in leaves(unknown.get(key))) for key in SECURITY_KEYS
        )):
            reasons.add("UNKNOWN_SECURITY_VALUE")
        if reasons:
            findings.append({"address": rc["address"], "reasons": sorted(reasons)})
    return {"environment": environment, "counts": counts,
            "risk": "HIGH RISK" if findings else "STANDARD REVIEW",
            "findings": sorted(findings, key=lambda f: f["address"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--environment", required=True, choices=["dev", "staging", "prod"])
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--fail-on-high-risk", action="store_true")
    args = parser.parse_args()
    try:
        result = summarize(json.loads(args.plan.read_text()), args.environment)
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(" ".join(f"{key}={value}" for key, value in result["counts"].items()))
        print(f"Risk: {result['risk']} (environment={args.environment})")
        for finding in result["findings"]:
            print(f"HIGH RISK {finding['address']}: {', '.join(finding['reasons'])}")
        print("Review required. Counts exclude data reads; replacements are not double-counted.")
    return 2 if args.fail_on_high_risk and result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
