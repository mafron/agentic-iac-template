#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
environment_name
terraform_version
opa_version
clean_cli_context
for variable in VAR_FILE BACKEND_CONFIG; do
  file="${!variable:-}"
  [[ "$file" == /* && -f "$file" && "$file" != *.example ]] || die "$variable must be an absolute existing non-example file"
done
cd "$ROOT"
dir="environments/$ENV"
umask 077
mkdir -p "$ROOT/.harness/plans/$ENV" "$ROOT/.harness/real/$ENV"
out="$(mktemp -d "$ROOT/.harness/plans/$ENV/run.XXXXXX")"
export TF_DATA_DIR="$ROOT/.harness/real/$ENV"
# No migrate-state/reconfigure/lock=false/refresh=false/target/destroy escape hatches.
terraform -chdir="$dir" init -input=false -lockfile=readonly -backend-config="$BACKEND_CONFIG" -no-color
terraform -chdir="$dir" validate -no-color
terraform -chdir="$dir" plan -input=false -lock-timeout=60s -var-file="$VAR_FILE" -out="$out/tfplan" -no-color >"$out/plan.txt"
terraform -chdir="$dir" show -json "$out/tfplan" >"$out/plan.json"
python3 scripts/plan_summary.py "$out/plan.json" --environment "$ENV" | tee "$out/summary.txt"
python3 - "$out" "$ENV" "$VAR_FILE" "$BACKEND_CONFIG" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
out = Path(sys.argv[1])
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
files = {'tfplan': out/'tfplan', 'plan.json': out/'plan.json',
         'variables': Path(sys.argv[3]), 'backend_config': Path(sys.argv[4])}
manifest = {'environment': sys.argv[2], 'commit': commit.stdout.strip() or 'UNCOMMITTED',
            'sha256': {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in files.items()}}
(out/'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY
echo "Review files: $out"
# Raw plan text/JSON can contain secrets. No automatic artifact upload or PR comment.
ENV="$ENV" PLAN_JSON="$out/plan.json" bash scripts/policy.sh | tee "$out/policy.txt"
if [[ "$ENV" == prod ]]; then
  python3 scripts/plan_summary.py "$out/plan.json" --environment prod --fail-on-high-risk
fi
echo 'Plan/policy complete. This does not authorize apply.'
