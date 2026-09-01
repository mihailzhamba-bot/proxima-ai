# Source inventory

Дата проверки: 2026-08-12. Этот файл фиксирует только provenance и границы импорта; secrets, ignored runtime artifacts и raw customer data не читались.

## torgstat-collector

- Source: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Торгстат-автоматизация/torgstat-collector`
- Tracked baseline: `610169a6bd3253fa351fa6fbe4ff571d4f4d5539`
- Remote: `https://github.com/mihailzhamba-bot/torgstat-collector.git`
- Verified 2026-08-12: `npm test` - 125/125 passed; `npm run typecheck` - exit 0.
- Import rule: add the tracked baseline under `services/collector/` with its commit provenance. Do not mutate, stash, commit or clean the source worktree.
- Dirty additions: PostgreSQL migration, ETL, pipeline, scheduler, backup and deployment files are candidates only. Before import, record relative path, byte SHA-256, review status and destination. Exclude `.env`, `auth/`, `config/`, `data/`, `logs/`, `manifests/`, `temp/` and any ignored runtime content.

## proxima-ai-manager

- Source: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Опрос-v2.2`
- Tracked baseline: `9cca25d1118ab74a113be43e4346a024b0c7abe7`
- Remote: `https://github.com/mihailzhamba-bot/proxima-ai-manager.git`
- Import rule: copy only contract, database, Data Health and test code explicitly required by M1. Do not import operational client artifacts, generated outputs, `.env`, caches or unrelated owner changes.

## Acceptance boundary

- Source worktrees remain untouched.
- Every imported file is tied to a source commit or explicit working-tree SHA-256.
- The monorepo root owns the combined verification command.
- Torgstat live session wiring remains absent until a separate signed gate.
