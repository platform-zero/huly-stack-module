#!/bin/sh
set -eu

# Huly registers its OIDC strategy only once during startup. Wait until the
# public issuer is available so a transient Keycloak/Caddy 502 cannot leave
# account permanently running without SSO.
: "${OPENID_ISSUER:?OPENID_ISSUER is required}"
attempt=0
while [ "$attempt" -lt 60 ]; do
  if node -e '
    const issuer = process.env.OPENID_ISSUER;
    const url = `${issuer.replace(/\/$/, "")}/.well-known/openid-configuration`;
    fetch(url, { signal: AbortSignal.timeout(5000) })
      .then(async response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const metadata = await response.json();
        if (metadata.issuer !== issuer) throw new Error("issuer mismatch");
      })
      .catch(error => { console.error(`OIDC discovery unavailable: ${error.message}`); process.exitCode = 1; });
  '; then
    exec node bundle.js
  fi
  attempt=$((attempt + 1))
  sleep 5
done
printf '%s\n' 'OIDC discovery did not become ready; exiting for service restart' >&2
exit 1
