package terraform.guardrails

import rego.v1

default allow := false

allow if {
  valid_context
  valid_plan
  count(deny) == 0
}

valid_context if data.context.environment in {"dev", "staging", "prod"}

valid_plan if {
  startswith(input.format_version, "1.")
  is_object(input.planned_values)
  input.complete == true
  input.errored == false
  is_array(object.get(input, "resource_changes", []))
}

deny contains "Invalid or missing trusted environment context" if not valid_context
deny contains "Invalid, errored or incomplete plan" if not valid_plan

resources contains rc if {
  some rc in object.get(input, "resource_changes", [])
  rc.mode == "managed"
}

# Explicitly list resources with tags; S3 subresources and associations lack tags.
# Expand this list alongside any new approved resource type.
taggable := {
  "aws_vpc", "aws_subnet", "aws_security_group", "aws_internet_gateway",
  "aws_route_table", "aws_s3_bucket", "aws_iam_policy", "aws_iam_role",
  "aws_kms_key", "aws_db_instance", "aws_rds_cluster",
  "aws_vpc_security_group_ingress_rule", "aws_vpc_security_group_egress_rule",
}
required_tags := {"Project", "Environment", "Owner", "ManagedBy"}

present_after(rc) if is_object(rc.change.after)

known_tag(rc, key) if {
  tags := object.get(rc.change.after, "tags", {})
  value := tags[key]
  is_string(value)
  trim_space(value) != ""
  unknown := unknown_attributes(rc)
  unknown_tags := object.get(unknown, "tags", {})
  not has_unknown(unknown_tags)
}

has_unknown(value) if {
  some path, leaf
  walk(value, [path, leaf])
  leaf == true
}

unknown_attributes(rc) := unknown if {
  unknown := object.get(rc.change, "after_unknown", {})
  is_object(unknown)
} else := {}

deny contains sprintf("%s: missing, empty or unknown required tag %s", [rc.address, key]) if {
  some rc in resources
  rc.type in taggable
  present_after(rc)
  some key in required_tags
  not known_tag(rc, key)
}

deny contains sprintf("%s: Environment tag does not match trusted environment", [rc.address]) if {
  some rc in resources
  rc.type in taggable
  present_after(rc)
  rc.change.after.tags.Environment != data.context.environment
}

deny contains sprintf("%s: ManagedBy must be Terraform", [rc.address]) if {
  some rc in resources
  rc.type in taggable
  present_after(rc)
  rc.change.after.tags.ManagedBy != "Terraform"
}

# Cover inline SG, legacy SG rules, and modern standalone ingress resources.
ingress_rules contains {"address": rc.address, "rule": rule} if {
  some rc in resources
  rc.type in {"aws_security_group", "aws_default_security_group"}
  present_after(rc)
  some rule in object.get(rc.change.after, "ingress", [])
}

ingress_rules contains {"address": rc.address, "rule": rc.change.after} if {
  some rc in resources
  rc.type == "aws_security_group_rule"
  rc.change.after.type == "ingress"
}

ingress_rules contains {"address": rc.address, "rule": rc.change.after} if {
  some rc in resources
  rc.type == "aws_vpc_security_group_ingress_rule"
  present_after(rc)
}

world_open(rule) if {
  some cidr in object.get(rule, "cidr_blocks", [])
  cidr == "0.0.0.0/0"
}
world_open(rule) if {
  some cidr in object.get(rule, "ipv6_cidr_blocks", [])
  cidr == "::/0"
}
world_open(rule) if object.get(rule, "cidr_ipv4", "") == "0.0.0.0/0"
world_open(rule) if object.get(rule, "cidr_ipv6", "") == "::/0"

allows_ssh(rule) if {
  protocol := object.get(rule, "ip_protocol", object.get(rule, "protocol", ""))
  protocol in {"-1", -1}
}
allows_ssh(rule) if {
  protocol := object.get(rule, "ip_protocol", object.get(rule, "protocol", ""))
  protocol in {"tcp", "6", 6}
  rule.from_port <= 22
  rule.to_port >= 22
}

deny contains sprintf("%s: internet ingress permits SSH (including all protocols or a port range)", [entry.address]) if {
  some entry in ingress_rules
  world_open(entry.rule)
  allows_ssh(entry.rule)
}

# Unknown IDs are normal. Unknown security decisions cannot be assumed safe.
security_fields := {
  "aws_security_group": ["ingress", "egress"],
  "aws_default_security_group": ["ingress", "egress"],
  "aws_security_group_rule": ["type", "protocol", "from_port", "to_port", "cidr_blocks", "ipv6_cidr_blocks"],
  "aws_vpc_security_group_ingress_rule": ["ip_protocol", "from_port", "to_port", "cidr_ipv4", "cidr_ipv6"],
  "aws_s3_bucket_public_access_block": ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"],
}

deny contains sprintf("%s: security attribute %s is unknown", [rc.address, key]) if {
  some rc in resources
  present_after(rc)
  some key in object.get(security_fields, rc.type, [])
  unknown := unknown_attributes(rc)
  has_unknown(object.get(unknown, key, false))
}

deny contains sprintf("%s: entire after value is unknown", [rc.address]) if {
  some rc in resources
  object.get(rc.change, "after_unknown", {}) == true
}

deny contains sprintf("%s: S3 public access control %s must be true", [rc.address, key]) if {
  some rc in resources
  rc.type == "aws_s3_bucket_public_access_block"
  present_after(rc)
  some key in security_fields.aws_s3_bucket_public_access_block
  object.get(rc.change.after, key, false) != true
}

# Environment comes from the caller even if the deleted resource had no tags.
# All managed deletions are denied in prod; replacements contain delete as well.
deny contains sprintf("%s: production deletion or replacement is forbidden", [rc.address]) if {
  data.context.environment == "prod"
  some rc in resources
  "delete" in rc.change.actions
}

deny contains sprintf("%s: state removal belongs to the break-glass workflow", [rc.address]) if {
  some rc in resources
  "forget" in rc.change.actions
}
deny contains sprintf("%s: import belongs to the separate state workflow", [rc.address]) if {
  some rc in resources
  object.get(rc.change, "importing", null) != null
}
deny contains sprintf("%s: address migration belongs to the separate state workflow", [rc.address]) if {
  some rc in resources
  object.get(rc, "previous_address", "") != ""
}
