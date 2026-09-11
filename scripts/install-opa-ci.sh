#!/usr/bin/env bash
# CI-only installer for the pinned Linux amd64 binary; no curl | sh.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ "$(uname -s)-$(uname -m)" == Linux-x86_64 ]] || die 'This installer is for Linux x86_64 CI only'
version="$(cat "$ROOT/.opa-version")"
[[ "$version" == 1.20.2 ]] || die 'Update the reviewed OPA SHA256 together with its version'
mkdir -p "$ROOT/.harness/bin"
curl --fail --silent --show-error --location --retry 3 \
  "https://github.com/open-policy-agent/opa/releases/download/v${version}/opa_linux_amd64_static" \
  -o "$ROOT/.harness/bin/opa"
echo "69da5179ee403d10fa11bab6cfb4ffb0d23dba5f9b682fa977db772a1da5670f  $ROOT/.harness/bin/opa" | sha256sum -c -
chmod 0755 "$ROOT/.harness/bin/opa"
if [[ -n "${GITHUB_PATH:-}" ]]; then echo "$ROOT/.harness/bin" >> "$GITHUB_PATH"; fi
