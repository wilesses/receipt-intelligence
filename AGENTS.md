# Receipt Tracker v2 Agent Guidance

Read `PROJECT_GUIDE.md` and `CURRENT_CONTEXT.md` before changing the project.
Those files remain the source of truth for workflow, data safety, documentation,
and verification.

## Ruflo orchestration

Ruflo is available for explicit multi-agent work through the project MCP
configuration. Use it only when the user requests agents, delegation, a swarm,
parallel work, or another task that clearly benefits from coordination.

- Prefer a hierarchical topology with one coordinator.
- Use at most four agents.
- Give every agent a bounded, non-overlapping task.
- Keep investigation agents read-only unless implementation is requested.
- Do not let multiple agents edit the same file concurrently.
- Preserve the SQLite database and all manual-review data.
- Database writes, schema changes, imports, backfills, and destructive actions
  still require the approvals specified in `CURRENT_CONTEXT.md`.
- Ruflo project memory, safe hooks, local learning, and bounded daemon
  autostart are enabled. Hook auto-execution and scheduled AI workers remain
  disabled, so they cannot silently edit files or consume model quotas.
- Autonomous loops, cloud MCP, and federation remain disabled unless the user
  explicitly requests them.
- Native Codex subagents remain the default for small parallel tasks. Use Ruflo
  when persistent task coordination or project memory materially helps.

Pinned CLI command:

```powershell
npx --yes ruflo@3.32.9 <command>
```

Operational details and examples are documented in `docs/Ruflo.md`.
