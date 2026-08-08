# Ruflo orchestration

Ruflo is configured as an optional, project-local orchestration layer for
Receipt Tracker v2. It provides swarm coordination, task routing, specialized
agents, and persistent project-scoped memory through an MCP server.

## Installed surface

- Ruflo CLI version: `3.32.9`, invoked through pinned `npx`.
- Runtime configuration: `.claude-flow/config.yaml`.
- Codex MCP configuration: `.codex/config.toml`.
- Topology: hierarchical, coordinator-led.
- Maximum agents: four.
- Memory: local SQLite with HNSW search and project-scoped memory graph under
  `.claude-flow/data`.
- Safe hooks, local neural learning, and bounded daemon autostart: enabled.
- Hook auto-execution and scheduled daemon AI workers: disabled.
- Cloud MCP and federation: disabled.
- Codex sandbox: `workspace-write`.
- Approval policy: `on-request`.

No global Codex or Claude configuration is modified.

## When to use it

Use Ruflo for work that has independent lanes, for example:

- parser investigation, test design, implementation, and review;
- separate backend, UI, E2E, and documentation workstreams;
- architecture or security audits with independent reviewers;
- long-running work that benefits from persistent task state.

Do not use it for a one-file edit, a small bug, copy changes, or routine CSS.

## Example requests

```text
Use Ruflo with a coordinator and three read-only agents. One inspects parser
edge cases, one maps test coverage, and one reviews data-safety risks. Combine
their evidence into one plan. Do not modify files or the database.
```

```text
Use Ruflo for this feature. Split the work into implementation, tests, and
independent review. Keep database writes and backfills out of scope.
```

## Useful commands

```powershell
npx --yes ruflo@3.32.9 init check
npx --yes ruflo@3.32.9 doctor
npx --yes ruflo@3.32.9 status
npx --yes ruflo@3.32.9 mcp list
npx --yes ruflo@3.32.9 swarm status
npx --yes ruflo@3.32.9 memory list
```

The daemon starts on Ruflo CLI use, runs at most two workers concurrently,
stops after 30 idle minutes, and has a maximum lifetime of 12 hours. Ruflo
3.32.9 registers its seven built-in schedules even when a narrower worker list
is present in YAML, so no unsupported worker filter is declared here. All of
those schedules run in local-only mode: scheduled AI workers are disabled to
prevent silent model-quota consumption.

Run mutating commands such as swarm initialization, autonomous loops, memory
clearing, or `doctor --fix` only when the requested task needs them and their
effects have been reviewed.

The MCP configuration is loaded when Codex starts a new project session. A
session that was already open before `.codex/config.toml` was created will not
gain Ruflo tools retroactively.

## Safety notes

The upstream Ruflo `3.32.9` initializer was not applied directly because its
Codex adapter `3.0.1` generates `approval_policy = "never"` together with
`sandbox_mode = "danger-full-access"` and attempts global MCP registration.
Its `--skip-claude` flag also generated Claude files during an isolated preview.
The project therefore uses a manually constrained configuration.

`ruflo memory init` and `ruflo memory stats` were observed starting the
background daemon even when autostart was disabled. Autostart is now explicitly
enabled and bounded by idle and lifetime limits. The daemon must not be confused
with scheduled AI workers: those remain disabled.

The package currently reports deprecated transitive npm dependencies. Keep the
version pinned and review release notes plus dependency health before upgrading.
