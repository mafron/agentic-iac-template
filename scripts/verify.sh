#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
cd "$ROOT"
mode="${1:-all}"
case "$mode" in all|fmt|validate|test|lint) ;; *) die "Unsupported verify mode: $mode" ;; esac
clean_cli_context

# Verify jobs receive no AWS credentials, including local profile or IMDS access.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
unset AWS_PROFILE AWS_DEFAULT_PROFILE AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN
unset AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI
export AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true

if [[ "$mode" == all ]]; then
  missing=0
  for tool in terraform tflint opa python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "NOT RUN: missing $tool" >&2
      missing=1
    fi
  done
  [[ "$missing" == 0 ]] || exit 1
fi
if [[ "$mode" != lint ]]; then terraform_version; fi
if [[ "$mode" == all || "$mode" == lint ]]; then tflint_version; fi
if [[ "$mode" == all ]]; then opa_version; fi
if [[ "$mode" == fmt ]]; then
  terraform fmt -recursive
  exit
fi
if [[ "$mode" == all ]]; then terraform fmt -check -recursive; fi

# Discover all module/environment roots in a stable order, including future roots.
mapfile -t roots < <(find modules environments -mindepth 2 -maxdepth 2 -name versions.tf -print | sort)
[[ "${#roots[@]}" -gt 0 ]] || die 'No Terraform roots found'
for version_file in "${roots[@]}"; do
  dir="${version_file%/versions.tf}"
  echo "Checking $dir ($mode)"
  export TF_DATA_DIR="$ROOT/.harness/verify/$dir"
  mkdir -p "$TF_DATA_DIR"
  if [[ "$mode" != lint ]]; then
    terraform -chdir="$dir" init -backend=false -lockfile=readonly -input=false -no-color
  fi
  if [[ "$mode" == all || "$mode" == validate ]]; then
    terraform -chdir="$dir" validate -no-color
  fi
  if [[ "$mode" == all || "$mode" == test ]]; then
    terraform -chdir="$dir" test -no-color
  fi
  if [[ "$mode" == all || "$mode" == lint ]]; then
    tflint --chdir="$dir" --config="$ROOT/.tflint.hcl" --format=compact
  fi
done
if [[ "$mode" == all ]]; then
  python3 -m unittest discover -s scripts/tests -v
  bash scripts/policy.sh test
fi
echo "PASS: $mode"
