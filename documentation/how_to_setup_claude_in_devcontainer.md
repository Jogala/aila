# How to set up Claude Code in the devcontainer

This guide documents how to authenticate Claude Code inside the VS Code devcontainer with the network firewall enabled, how to forward the OAuth callback port, and notes a couple of alternative setups.

## Overview

- The devcontainer installs the Claude Code CLI and runs a strict egress firewall from `.devcontainer/init-firewall.sh`.
- Claude Code uses an OAuth flow that redirects to `http://localhost:<random-port>/callback` where the CLI listens inside the container.
- You must forward that exact port from your host to the container during login.

## Prerequisites

- Devcontainer opens successfully in VS Code.
- Firewall script exists at: `.devcontainer/init-firewall.sh`.
- The firewall script currently allows these domains:
  - `registry.npmjs.org`, `api.anthropic.com`, `claude.ai`, `www.anthropic.com`, `sentry.io`, `statsig.anthropic.com`, `statsig.com`
- The script has been made idempotent (uses `ipset add -exist` and de-duplicates A records) to avoid failures on duplicate IPs.

Re-apply the firewall at any time:

```
sudo /usr/local/bin/init-firewall.sh
```

## Authenticate Claude Code inside the container

1) Start the CLI and copy the login URL

```
claude
```

The CLI prints an OAuth URL that includes a `redirect_uri` with a localhost port, for example:

```
https://claude.ai/oauth/authorize?...&redirect_uri=http%3A%2F%2Flocalhost%3A34365%2Fcallback&...
```

2) Read the callback port from the URL

- `redirect_uri=http%3A%2F%2Flocalhost%3A34365%2Fcallback`
- Decoded: `http://localhost:34365/callback` → the port is `34365`.

Handy one‑liner (paste the whole URL as the argument):

```
python - <<'PY' "PASTE_URL_HERE"
from urllib.parse import urlparse, parse_qs, unquote
import sys
q = parse_qs(urlparse(sys.argv[1]).query)
ru = unquote(q['redirect_uri'][0])
print('redirect_uri:', ru)
print('port:', urlparse(ru).port)
PY
```

3) Forward that exact port in VS Code

- Open the Ports panel → Forward a Port → enter the port number (e.g., `34365`).
- Ensure the Local Address is `localhost:34365` (right‑click → Change Local Port… if needed).
- Keep the terminal where `claude` is running open.

4) Complete the browser flow

- Open the OAuth URL that `claude` printed and click Authorize.
- With the port forwarded, the container’s local callback server receives the code and finishes auth.

5) Verify

```
claude chat
```

You should be able to send a quick prompt.

## Troubleshooting

- Connection refused after clicking Authorize:
  - Most likely the forwarded port doesn’t match the `redirect_uri` port. Forward the exact port shown by `claude`.
  - Check the CLI is listening on that port inside the container:
    - `ss -ltnp | rg <PORT>` (expect LISTEN on 127.0.0.1:<PORT> from a node process).
  - Re-run `claude` to generate a fresh URL if needed and forward the new port.

- Firewall setup fails on duplicate IPs:
  - The script was updated to de‑duplicate and use `ipset add -exist`. Re-run:
    - `sudo /usr/local/bin/init-firewall.sh`

- Firewall domain resolution fails (NXDOMAIN):
  - Only `api.anthropic.com` and `claude.ai` are required for the OAuth and token exchange. The script will error if a domain can’t be resolved; re-run later to refresh IPs.

## Where your Claude credentials live

- The container mounts `/home/node/.claude` from a Docker named volume defined in `.devcontainer/devcontainer.json`.
- Named volumes persist across rebuilds, but are not visible as regular files on your host.
- Inspect volumes on the host:
  - `docker volume ls | grep claude-code-config`
  - `docker volume inspect <VOLUME_NAME>`

## Alternatives (not tested)

- Host bind for credentials (browseable on host):
  - Change the mount in `.devcontainer/devcontainer.json` from a named volume to a host bind:
    - From: `source=claude-code-config-${devcontainerId},target=/home/node/.claude,type=volume`
    - To: `source=${localEnv:HOME}/.claude,target=/home/node/.claude,type=bind,consistency=cached`
  - Ensure permissions on host: `mkdir -p ~/.claude && chmod 700 ~/.claude`
  - You can migrate existing data from the old volume using a temporary container to copy files.

- API key auth (skip OAuth/device callback):
  - Set `ANTHROPIC_API_KEY` in the container environment before launching `claude`, or bridge `AILA_ANTHROPIC_API_KEY` from the host into the container via `containerEnv` in `devcontainer.json`.
  - This avoids browser-based auth entirely.

## Managing forwarded ports

- You only need to keep the current OAuth callback port forwarded while authenticating.
- Previously forwarded ports (e.g., `42995`) can be removed from the Ports panel once you complete auth.

