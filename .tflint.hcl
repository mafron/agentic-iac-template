# Terraform ruleset is bundled with the pinned TFLint binary; no AWS API/plugin.
plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
