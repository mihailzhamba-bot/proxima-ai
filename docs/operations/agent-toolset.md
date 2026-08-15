# Agent toolset inventory

Evidence captured on 2026-08-15 for Jira PA-30. Status values are `configured`, `missing` or `N/A`. No credential values or business data are recorded here.

| Интеграция | Статус | Evidence / limitation | Owner / action |
|---|---|---|---|
| Sentry | missing | Repository scan and `codex mcp list` on 2026-08-15 found no error collector | Owner: Mike; Next: create a Sentry project and read-only agent connection before the first pilot release |
| GitHub | configured | Fine-grained PAT limited to `mihailzhamba-bot/proxima-ai` is stored in macOS Keychain; repository read, Actions read and `git push --dry-run` passed on 2026-08-15 after the previous broad OAuth grant was revoked | - |
| Chrome DevTools | configured | Chrome extension returned the Atlassian DOM and console logs on 2026-08-15; the browser Jira session itself is not authenticated | - |
| PostgreSQL | configured | Staging provisioning and idempotent rerun passed on 2026-08-15; SELECT succeeded while DML and DDL probes were rejected; the secret file is `root:root 0600` | Role attributes deny superuser, createDB, createRole, replication and bypassRLS |
| Jira | configured | Official Atlassian MCP read of PA-30 passed on 2026-08-15; `.codex/config.toml` exposes only read tools | Residual: upstream OAuth also has `write:jira-work`; project allowlist is the accepted mitigation |
| Confluence | N/A | Confluence spaces returned 404 and Rovo search reported that the app is not installed on 2026-08-15 | Reason: the Atlassian site currently exposes Jira only |
| jq / rg | configured | `command -v` and version smoke passed on 2026-08-15 | - |

## GitHub target permissions

The replacement fine-grained PAT is restricted to `mihailzhamba-bot/proxima-ai` with `Contents: read/write`, `Pull requests: read/write`, `Actions: read` and implicit metadata access. Issues, Administration, organization, gist and workflow-write permissions stay disabled. Store it in macOS Keychain through `gh`; never pass it in chat, command arguments, logs or Git.

## PostgreSQL operation

Deploy from the clean checkout on the staging VPS:

```bash
sudo bash /srv/proxima-ai/repo/infra/bootstrap/provision-postgres-diagnostics.sh
```

The installer creates a root-only password file outside Git and installs `proxima-psql-readonly`. The wrapper accepts SQL only on stdin, authenticates directly as `proxima_diagnostics` over the container-local socket, and uses fail-closed `psql` settings. It must never query customer rows during a smoke test.

## Smoke tests

Run the tracked and live checks:

```bash
make secrets
make agent-toolset
make verify
```

`make agent-toolset` checks the CLI prerequisites and project config. When an integration is marked `configured`, it also tests GitHub read/dry-run write access and PostgreSQL SELECT plus rejected DML/DDL. `missing` is accepted only with both an owner and next action; `N/A` is accepted only with a reason.

Jira and Chrome are MCP/browser surfaces, so their live smoke remains an agent action: read PA-30 through the Jira MCP, then read one DOM snapshot and console-log sample through Chrome DevTools without submitting a form.
