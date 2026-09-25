#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
validator="${WEBSERVICES_MODULE_CONTRACT_VALIDATOR:-}"
if [ -z "$validator" ]; then
  for candidate in     "$repo_root/../../sso-stack-generator/scripts/modules/module-contract.sh"     "$repo_root/../sso-stack-generator/scripts/modules/module-contract.sh"; do
    if [ -x "$candidate" ]; then
      validator="$candidate"
      break
    fi
  done
fi
[ -n "$validator" ] || { printf '[module-contract] set WEBSERVICES_MODULE_CONTRACT_VALIDATOR or keep sso-stack-generator next to modules workspace\n' >&2; exit 1; }
"$validator" validate "$repo_root"
grep -Fq 'OPENID_ISSUER: "http://host.containers.internal:25007/realms/webservices"' "$repo_root/stack.runtime.yaml"
grep -Fq 'BRANDING_PATH: "/usr/src/app/brandings.json"' "$repo_root/stack.runtime.yaml"
grep -Fq '"./configs/huly/brandings.json:/usr/src/app/brandings.json:ro"' "$repo_root/stack.runtime.yaml"
grep -Fq '"huly.{{DOMAIN}}"' "$repo_root/stack.config/huly/brandings.json.template"
grep -Fq '"key": "webservices"' "$repo_root/stack.config/huly/brandings.json.template"
