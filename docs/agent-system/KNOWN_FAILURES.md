# KNOWN_FAILURES — PROXIMA AI

| ID | Item | Reason | Owner | Task | Introduced | Expected resolution | Policy |
|---|---|---|---|---|---|---|---|
| KF-1 | ~~Pre-existing dirty tree (Makefile, tools/verify_runtime_boundary.py, .planning/STATE.md, untracked .mcp.json/opencode.json/.codex/)~~ RESOLVED 2026-08-17: those files are committed, `git status` reports a clean tree | other threads' work | Mike | closed by backlog audit 2026-08-17 | pre-2026-08-16 | done | CLOSED |
| KF-2 | ~~TASKS.md references HEAD 1a211c9 while repo HEAD moved past it~~ RESOLVED 2026-08-16 (task snapshot wording updated) | task snapshot drift | agent | fixed in remediation wave 2 | 2026-08-16 | done | CLOSED |

No test-level known failures: `make verify` must stay green; any red test = immediate register-or-fix.
