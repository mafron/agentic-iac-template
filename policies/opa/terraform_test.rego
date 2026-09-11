package terraform.guardrails_test

import rego.v1
import data.terraform.guardrails

tags := {"Project": "harness", "Environment": "dev", "Owner": "platform", "ManagedBy": "Terraform"}

resource(kind, actions, after, unknown) := {
  "address": sprintf("%s.example", [kind]), "type": kind, "mode": "managed",
  "change": {"actions": actions, "before": null, "after": after, "after_unknown": unknown},
}
plan(changes) := {
  "format_version": "1.2", "terraform_version": "1.16.2", "planned_values": {},
  "complete": true, "errored": false, "resource_changes": changes,
}
dev := {"environment": "dev"}
prod := {"environment": "prod"}

test_safe_tags_and_unknown_id if {
  rc := resource("aws_s3_bucket", ["create"], {"tags": tags}, {"id": true})
  guardrails.allow with input as plan([rc]) with data.context as dev
}

test_empty_plan_is_valid if {
  guardrails.allow with input as plan([]) with data.context as dev
}

test_missing_context_fails_closed if {
  not guardrails.allow with input as plan([]) with data.context as {}
}

test_invalid_plan_fails_closed if {
  not guardrails.allow with input as {} with data.context as dev
}

test_missing_and_unknown_tags_denied if {
  missing := resource("aws_s3_bucket", ["create"], {"tags": {"Environment": "dev"}}, {})
  unknown := resource("aws_s3_bucket", ["create"], {"tags": tags}, {"tags": {"Owner": true}})
  every rc in [missing, unknown] {
    not guardrails.allow with input as plan([rc]) with data.context as dev
  }
}

test_empty_owner_denied if {
  rc := resource("aws_iam_role", ["create"], {"tags": object.union(tags, {"Owner": " "})}, {})
  not guardrails.allow with input as plan([rc]) with data.context as dev
}

test_inline_ipv4_ssh_range_denied if {
  rule := {"protocol": "tcp", "from_port": 20, "to_port": 25, "cidr_blocks": ["0.0.0.0/0"]}
  rc := resource("aws_security_group", ["create"], {"tags": tags, "ingress": [rule]}, {})
  not guardrails.allow with input as plan([rc]) with data.context as dev
}

test_modern_ipv6_all_protocols_denied if {
  rc := resource("aws_vpc_security_group_ingress_rule", ["create"], {"tags": tags, "ip_protocol": "-1", "cidr_ipv6": "::/0"}, {})
  not guardrails.allow with input as plan([rc]) with data.context as dev
}

test_legacy_ssh_denied if {
  rc := resource("aws_security_group_rule", ["create"], {"type": "ingress", "protocol": "6", "from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]}, {})
  not guardrails.allow with input as plan([rc]) with data.context as dev
}

test_egress_ssh_is_not_ingress if {
  rc := resource("aws_security_group_rule", ["create"], {"type": "egress", "protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]}, {})
  guardrails.allow with input as plan([rc]) with data.context as dev
}

test_private_ssh_and_public_https_allowed if {
  private := {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": ["10.42.0.0/16"]}
  https := {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]}
  every rule in [private, https] {
    rc := resource("aws_security_group", ["create"], {"tags": tags, "ingress": [rule]}, {})
    guardrails.allow with input as plan([rc]) with data.context as dev
  }
}

test_unknown_security_denied if {
  rc := resource("aws_security_group", ["update"], {"tags": tags}, {"ingress": true})
  not guardrails.allow with input as plan([rc]) with data.context as dev
}

test_untagged_prod_delete_denied if {
  rc := resource("aws_s3_bucket", ["delete"], null, {})
  not guardrails.allow with input as plan([rc]) with data.context as prod
}

test_both_replacement_orders_denied_in_prod if {
  every actions in [["create", "delete"], ["delete", "create"]] {
    rc := resource("aws_s3_bucket", actions, {"tags": object.union(tags, {"Environment": "prod"})}, {})
    not guardrails.allow with input as plan([rc]) with data.context as prod
  }
}

test_relabeling_does_not_bypass_environment if {
  rc := resource("aws_s3_bucket", ["create"], {"tags": tags}, {})
  not guardrails.allow with input as plan([rc]) with data.context as prod
}

test_nonprod_delete_allowed_by_this_policy if {
  rc := resource("aws_s3_bucket", ["delete"], null, {})
  guardrails.allow with input as plan([rc]) with data.context as dev
}

test_s3_block_disable_denied if {
  rc := resource("aws_s3_bucket_public_access_block", ["update"], {"block_public_acls": false}, {})
  not guardrails.allow with input as plan([rc]) with data.context as dev
}

test_state_forget_denied if {
  rc := resource("aws_s3_bucket", ["forget"], null, {})
  not guardrails.allow with input as plan([rc]) with data.context as dev
}

test_import_and_move_denied if {
  base := resource("aws_s3_bucket", ["no-op"], {"tags": tags}, {})
  imported := object.union(base, {"change": object.union(base.change, {"importing": {"id": "test"}})})
  moved := object.union(base, {"previous_address": "aws_s3_bucket.old"})
  every rc in [imported, moved] {
    not guardrails.allow with input as plan([rc]) with data.context as dev
  }
}
