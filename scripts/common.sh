#!/usr/bin/env bash
# Shared plumbing, not a security sandbox. IAM remains the actual boundary.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export LC_ALL=C TF_IN_AUTOMATION=1 TF_INPUT=0

die() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing tool: $1"; }
environment_name() {
  case "${ENV:-}" in dev|staging|prod) ;; *) die 'ENV must be dev, staging or prod' ;; esac
}
terraform_version() {
  need terraform
  need python3
  local actual
  actual="$(terraform version -json | python3 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])')"
  [[ "$actual" == "$(cat "$ROOT/.terraform-version")" ]] || die 'Terraform version differs from .terraform-version'
}
tflint_version() {
  need tflint
  local actual
  actual="$(tflint --version | head -n 1)"
  [[ "$actual" == "TFLint version $(cat "$ROOT/.tflint-version")" ]] || die 'TFLint version differs from .tflint-version'
}
opa_version() {
  need opa
  local actual
  actual="$(opa version | head -n 1)"
  [[ "$actual" == "Version: $(cat "$ROOT/.opa-version")" ]] || die 'OPA version differs from .opa-version'
}
clean_cli_context() {
  local variable
  for variable in ${!TF_CLI_ARGS@}; do
    [[ -z "${!variable}" ]] || die "Unset $variable; wrappers use explicit arguments"
  done
  [[ "${TF_WORKSPACE:-default}" == default ]] || die 'Use default workspace; roots isolate environments'
  export TF_WORKSPACE=default
}
