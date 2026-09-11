#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
opa_version
if [[ "${1:-}" == test ]]; then
  opa check --strict "$ROOT/policies/opa"
  opa test "$ROOT/policies/opa" -v
  ENV=dev PLAN_JSON="$ROOT/fixtures/plans/safe.json" bash "$ROOT/scripts/policy.sh"
  set +e
  ENV=prod PLAN_JSON="$ROOT/fixtures/plans/unsafe.json" bash "$ROOT/scripts/policy.sh"
  code=$?
  set -e
  [[ "$code" == 1 ]] || die "Unsafe fixture must be rejected with status 1, got $code"
  exit 0
fi
environment_name
[[ -n "${PLAN_JSON:-}" && -f "$PLAN_JSON" ]] || die 'Set PLAN_JSON to an existing terraform show -json file'
need python3
# Structural validation rejects incomplete/state/malformed JSON before policy evaluation.
python3 "$ROOT/scripts/plan_summary.py" "$PLAN_JSON" --environment "$ENV" >/dev/null
umask 077
mkdir -p "$ROOT/.harness"
context="$(mktemp "$ROOT/.harness/policy-context.XXXXXX.json")"
trap 'rm -f -- "$context"' EXIT
# Environment is a wrapper argument, never inferred from resource tags.
python3 - "$ENV" "$context" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[2]).write_text(json.dumps({"context": {"environment": sys.argv[1]}}))
PY
args=(--data "$ROOT/policies/opa/terraform.rego" --data "$context" --input "$PLAN_JSON" --strict-builtin-errors)
opa eval "${args[@]}" --format pretty 'data.terraform.guardrails.deny'
# --fail on the equality query makes false/undefined fail, unlike printing deny alone.
opa eval "${args[@]}" --format pretty --fail 'data.terraform.guardrails.allow == true'
