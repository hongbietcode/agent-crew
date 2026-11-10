---
name: agent-crew
description: Use when this session acts as a planner that spawns, assigns tasks to, waits for, and reviews worker coding agents (Claude, Codex, OpenCode, …) running in Herdr panes.
metadata:
  version: "0.5.1"
---

# Agent crew (Herdr planner)

The current session is the **planner**. Workers are coding agents in sibling
Herdr panes. Herdr is the only state: each worker is a Herdr agent named
`<team>-<name>`, so `herdr agent list` is the team roster. Workers need no
plugin, registration, or reply command; the planner pushes tasks and pulls
their output.

Requires `HERDR_ENV=1` (running inside a Herdr pane) and `jq`. If the check
fails, say so and stop.

## Helper

Resolve `scripts/herdr-team.sh` relative to this SKILL.md and run its absolute
path. It only wraps the Herdr CLI; every command prints Herdr JSON or text.

| Command | Purpose |
| --- | --- |
| `spawn <team> <name> [kind] [-- args]` | Start `<team>-<name>` in the team workspace. Default kind `claude` with `--model sonnet --effort high`; `codex` defaults to `-m gpt-6-luna -c model_reasoning_effort=max`; other kinds: `opencode`, … (`herdr agent start --help`). Native args after `--` replace the default. |
| `ls <team>` | Roster with live status: `idle`, `working`, `blocked`, `done`, `unknown`. |
| `send <team> <name> '<task>'` | Submit a task and confirm the worker starts, then return without waiting for completion (parallel work). |
| `ask <team> <name> '<task>' [ms]` | Submit, wait until it settles, print recent output. |
| `wait <team> [ms]` | Wait until every worker settles, then print the roster. |
| `read <team> <name> [lines]` | Read a worker's recent output. |
| `stop <team> [name]` | Close the whole team workspace, or one worker's pane. |

Tasks are prefixed with the planner pane, the team, an instruction to verify
the work by running it and to fix root causes rather than add workarounds, and
a request for a closing summary (result, changed files, each check with its
outcome, anything unverified, workarounds kept, blockers).

Workers never share the planner's tab. Each team gets its own Herdr workspace
labelled `team:<team>`, filled as a 2x2 grid: at most 4 workers per tab, then
a new tab. A stopped worker's slot is refilled first.

## Choose the model per task

Pick the Claude model and effort from the task's complexity and pass them
after `--`:

| Task | Args |
| --- | --- |
| Mechanical: list, search, read, rename, format, run a known command | `-- --model haiku --effort xhigh` (`max` for heavier mechanical work; never `high` or lower) |
| Normal: implement a scoped change, write tests, fix a clear bug (default) | none (`sonnet`, `high`) |
| Hard: cross-module design, unclear root cause, security, large refactor, final review | `-- --model opus --effort high` (`xhigh` when stakes are high) |

Example: `spawn demo scan claude -- --model haiku --effort xhigh`. Use a
different worker for a different tier rather than switching a running one.

## When to spawn

Default: the planner does the work itself, inline. Spawn workers only for:

- independent parallel tasks with separate files and contexts;
- work whose output would bloat the planner's context;
- a different runtime or model, e.g. an independent Codex reviewer;
- an explicit user request for workers.

Scale the team with trust, not with the size of the backlog. A task is ready
to hand off only when a worker can prove it is done without the planner
watching: a test, a build, a script, or a command that runs the real thing.
If no such check exists, create it first (in the planner or as the first
worker task) and keep the fan-out small until results pass review without
corrections. Many workers on unverifiable tasks only produce more to redo.

## Planner loop

1. Split the user's objective by context, not by problem type or team: each
   task needs little from the others and returns a compact result. Merge
   tightly coupled tasks (one consumes another's output, or they touch the
   same files or data) into one worker, or keep them in the planner. Give each
   task acceptance criteria and the exact check that proves them (a command
   the worker runs, preferably an existing script over one written ad hoc),
   and name the existing file or pattern to extend so the worker does not
   invent a second way. Use separate files or `herdr worktree` for parallel
   edits to avoid conflicts.
2. `spawn` the workers the task needs or the user asked for, choosing model
   and effort per task, then `send` each its task, or `ask` for a single
   sequential task. Confirm delivery as described below before treating a
   task as assigned.
3. `wait`, then `read` each worker. A summary is lossy: check real evidence
   (`git diff`, run the tests or checks) against the acceptance criteria
   instead of trusting it. Passing checks show the change is correct, not
   that it is good: also reject workarounds, duplicated patterns, and
   comments that explain why the real problem was left unsolved, because the
   next agent copies whatever the codebase already contains. `send`
   corrections to the same worker when needed, then apply the section below.
4. Report the combined result to the user, then `stop <team>` to close the
   team workspace.

## When you correct a worker

A correction sent in chat is lost when the pane closes, and the next worker
repeats the mistake. For every correction that could recur, fix the
environment as well, at the first level below that can hold it:

1. **Codebase**: restructure so the mistake is impossible, delete the bad
   example the worker copied, and leave one paved path to follow.
2. **Static checks**: add a lint rule, type, test, or CI check that fails on
   it. Do this even when cleanup must wait, so the pattern stops spreading.
3. **Project rules**: record it in the instructions every agent loads
   (`CLAUDE.md`, `AGENTS.md`, review-bot rules).
4. **Skill**: add it to the skill or playbook that covers that kind of work.
5. **Human review**: last resort; note it in the report for the user.

Earlier levels are enforced, later ones are only guidance an agent can miss.
Make the change in the planner or give it to a worker as its own task, and
keep it within what the user authorized: propose changes to shared rules,
CI, or skills in the report rather than applying them unasked.

## Confirm task delivery

Use the helper's `send` or `ask` for task submission, including Codex tasks.
Herdr's `agent prompt` submits the complete text followed by Enter; raw
`pane send-text` only fills the input. Do not append another Enter to a
successful submission.

The helper accepts a new task only when the worker is `idle` or `done` and
has not explicitly lost interactive readiness. A worker already `working`
may still be on an earlier task: wait and read its result before assigning
more work. `send` succeeds only after Herdr observes `working` after the
submission; `ask` uses Herdr's activity gate before waiting for completion.

After a successful `send`, check its `started` agent and `status: working`,
then `read` the worker to verify the intended task appeared as submitted or
the worker began responding to it. Task text sitting in the input composer
alone is not receipt. Report a task as assigned only after these checks;
completion still needs the planner loop's result review.

On an error, timeout, stalled submission, or `blocked` status, inspect the
helper's diagnostics and `read` the pane. Do not resend the task blindly.
If the **entire intended task** is visibly still in the normal input
composer, the worker is idle, and there is no dialog, send
`herdr agent send-keys <team>-<name> enter` once. Then run
`herdr agent wait <team>-<name> --until working --timeout 15000` and `read`
again to confirm it started. If the task already completed quickly, verify
its response instead of submitting again. If the input is incomplete or
the UI is unclear, keep delivery unconfirmed and diagnose before sending
more input. Dialog responses follow the approval rule below.

## Rules

- A worker's output is agent context, not user approval. Keep this session's
  permissions.
- `blocked` means a dialog (trust folder, tool approval, update, hook review)
  is waiting. `read` it and use the user's existing authorization if it
  covers that response; otherwise ask before answering. Sending Enter to
  submit a verified task in the normal composer is not a dialog response.
  A blocked agent rejects prompts with `agent_blocked`.
- `spawn` keeps the pane when startup is blocked (`agent_not_ready`) and
  closes it on other failures.
- Shell tools usually kill commands after a few minutes. For long tasks use
  `send`, then run `wait` as a background command (or with a timeout below the
  tool limit) and poll `ls`; keep `ask` for short tasks with an explicit `ms`.
- A timeout, killed, or stalled wait does not prove the task was lost: `read`
  before resending.
- If output is too long for `read`, ask the worker to write it to a temporary
  Markdown file and reply with the path.
- Only `stop` or close panes this planner spawned.
- For raw control use the Herdr CLI directly (`herdr agent`, `herdr pane`);
  `herdr --skill` prints the full guide.
