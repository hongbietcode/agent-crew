# Agent Crew

**Run a team of coding agents from one session.** Agent Crew turns your Claude
Code or Codex session into a *planner* that splits work, starts worker agents
(Claude, Codex, OpenCode, …) in [Herdr](https://herdr.dev) panes, hands them
tasks, waits for them, and checks their results before anything reaches you.

It is one skill and one POSIX shell script on top of the Herdr CLI. There is no
daemon, no registry, no server, and nothing to install on the workers.

```text
                ┌──────────────────────────────┐
   you ───────▶ │  Planner (Claude Code/Codex) │  splits work, picks models,
                │  + agent-crew skill          │  reviews diffs, reports back
                └──────────────┬───────────────┘
                               │ herdr-team.sh  (spawn / send / wait / read)
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
   │ demo-a      │      │ demo-b      │      │ demo-cx     │
   │ Claude Opus │      │ Claude Haiku│      │ Codex Sol   │   Herdr panes,
   │ medium      │      │ xhigh       │      │ xhigh       │   2x2 grid per tab
   └─────────────┘      └─────────────┘      └─────────────┘
```

## Why

- **Parallel work without context bloat.** Independent tasks (audit two
  packages, fix three unrelated bugs) run side by side. Each worker keeps its
  own context, so the planner only receives compact results.
- **The right model for each task.** Mechanical work goes to a cheap model and
  hard work goes to a strong one. The defaults come from cost-per-task data
  (see [Model routing](#model-routing)), not from the price per token.
- **Mix runtimes.** Have Claude write a fix and Codex review it independently,
  or add OpenCode or any other agent that Herdr can start.
- **Results are verified.** Every task ships with the check that proves it is
  done. The planner reads `git diff` and runs the tests itself instead of
  trusting a worker's summary.
- **Mistakes don't recur.** When the planner corrects a worker, it also fixes
  the codebase, the checks, or the rules, so the next worker can't make the same
  mistake.
- **Nothing hidden.** Herdr is the only state. A worker is just a Herdr agent
  named `<team>-<name>`, so you can watch every pane and `herdr agent list` is
  the team roster.

## How it works

| Role | What it does |
| --- | --- |
| **Planner** | The session that loaded the skill. It splits the objective, spawns workers, assigns tasks, waits, reviews the evidence, and reports to you. Only the planner holds state. |
| **Worker** | An ordinary agent in a Herdr pane. It needs no plugin and runs no reply command; the planner reads its output through Herdr. |
| **Team** | A Herdr workspace labelled `team:<team>`, laid out as a 2x2 grid (at most 4 workers per tab; a full tab opens a new one, and slots freed by `stop` are filled first). Workers never share the planner's tab. |

The planner loop:

1. **Split** the objective by context, so each task needs little from the
   others. Give every task acceptance criteria and the exact command that
   proves it.
2. **Spawn** the workers, choosing model and effort per task, and **send**
   each its task. Delivery is confirmed only when Herdr sees the worker start
   working.
3. **Wait**, **read**, and check the real evidence: the diff and the tests.
   Reject workarounds and duplicated patterns even when the checks pass.
4. **Report** the combined result and **stop** the team.

## Model routing

Price per token is misleading. What matters is the **cost per task**: a strong
model often finishes in fewer tokens. The defaults below follow the Artificial
Analysis Intelligence Index, plotted as score against cost per task.

### Claude workers

| Task | Model and effort | Args after `--` |
| --- | --- | --- |
| Mechanical: list, search, read, rename, format, run a known command | Haiku `xhigh` (`max` for heavier mechanical work) | `--model haiku --effort xhigh` |
| **Normal (default):** implement a scoped change, write tests, fix a clear bug | **Opus `medium`** | none |
| Hard: cross-module design, unclear root cause, security, large refactor | Opus `high` | `--model opus --effort high` |
| Critical: final review, security sign-off, high-stakes design | Opus `xhigh` | `--model opus --effort xhigh` |

Why not Sonnet? On cost per task, Opus is ahead at every effort level:

| Comparison | Score | Cost per task |
| --- | --- | --- |
| Opus 5.5 `medium` vs Sonnet 5.5 `high` | ~51 vs ~47 | ~$1.4 vs ~$1.1 |
| Opus 5.5 `xhigh` vs Sonnet 5.5 `max` | ~56 vs ~56 | $3.46 vs $7.60 (2.2x) |

Opus `max` is also avoided: it costs about 1.7x `xhigh` for about 1.5 more
points.

### Codex workers

| Task | Model and effort | Args after `--` |
| --- | --- | --- |
| Mechanical, high-volume, easy to check | Terra 6.1 `low` | `-m gpt-6.1-terra -c model_reasoning_effort=low` |
| **Normal (default)** | **Sol 6.1 `medium`** | none |
| Hard task or independent review | Sol 6.1 `xhigh` | `-m gpt-6.1-sol -c model_reasoning_effort=xhigh` |
| Highest score regardless of cost | Astra `max` | `-m gpt-6-astra -c model_reasoning_effort=max` |

Intelligence Index v5.0, score · cost per task:

| Effort | Astra | Sol 6.1 | Terra 6.1 | Luna |
| --- | --- | --- | --- | --- |
| max | 57 · $6.24 | 55 · $1.27 | 51 · $0.96 | 28 · $0.15 |
| xhigh | 55 · $3.66 | 52 · $0.76 | 45 · $0.40 | 23 · $0.10 |
| high | 55 · $3.24 | 50 · $0.59 | 42 · $0.26 | 21 · $0.07 |
| medium | 51 · $2.73 | 46 · $0.36 | 38 · $0.17 | 18 · $0.04 |
| low | 43 · $1.42 | 35 · $0.16 | 29 · $0.07 | 10 · $0.01 |

What the table shows:

- Luna above `low` loses to Terra `low`, which scores higher at similar or
  lower cost.
- Sol `max` matches Astra `high` for about 40% of the cost, and Astra below
  `max` loses to Sol everywhere.
- On the Coding Agent Index (Codex harness), Sol `medium` scores 61.4 at $0.70
  while Sol `max` scores 60.1 at $1.55, so `max` is skipped. Sol `xhigh` (62.9
  at $1.04) is the value peak for hard coding work.

> Benchmarks move. Figures come from Artificial Analysis via
> [Respan](https://www.respan.ai/articles/gpt-6-sol-vs-luna-vs-astra) (Codex,
> Nov 2026), [Preuve](https://preuve.ai/blog/ai-coding-models-statistics-2026)
> (Coding Agent Index, Oct 2026), and a Respan chart for Claude (Sep 2026).
> Compare numbers only within one table, since index versions differ. Override
> any default per worker with native args after `--`.

## Requirements

- [Herdr](https://herdr.dev) is running, and the planner sits in a Herdr pane
  (`HERDR_ENV=1`).
- The Herdr integration is installed for every agent you use as a worker.
  Check with `herdr integration status`; Herdr needs it to detect
  `idle`/`working`/`blocked`/`done`.
- `jq` (macOS ships `/usr/bin/jq`).

## Installation

Claude Code:

```text
/plugin install agent-crew --marketplace hongbietcode/agent-crew
```

Codex uses the `.codex-plugin/plugin.json` manifest:

```bash
codex plugin add agent-crew@personal
```

For local development: `claude --plugin-dir /path/to/agent-crew`.

## Quick start

Ask the planner in plain language:

> Use agent-crew, team demo: audit the independent packages svc-a and svc-b in
> parallel, one worker per package; verify the findings and fix them yourself,
> then have a codex worker named cx independently review the fix.

Or drive the script directly:

```bash
T=/path/to/agent-crew/skills/agent-crew/scripts/herdr-team.sh

$T spawn demo a                   # Claude Opus medium (default)
$T spawn demo scan claude -- --model haiku --effort xhigh    # mechanical work
$T spawn demo cx codex            # Codex GPT-6.1 Sol medium (default)
$T spawn demo b opencode          # any other Herdr agent kind

$T send demo a 'Audit packages/svc-a: hardcoded secrets, unsafe SQL; list file:line.'
$T send demo scan 'List every TODO in packages/ with file:line.'
$T wait demo                      # until every worker is idle/done/blocked
$T read demo a                    # read the summary, then open file:line yourself
$T ask demo cx 'Review the git diff of the fix; report bugs only.' 600000
$T ls demo
$T stop demo                      # close the team workspace
```

## Commands

| Command | What it does |
| --- | --- |
| `spawn <team> <name> [kind] [-- args]` | Start `<team>-<name>` in the team workspace. `kind` defaults to `claude`; native args after `--` replace the default model and effort. |
| `send <team> <name> <message>` | Submit a task and confirm within 15 s that the worker started (not that it finished). |
| `ask <team> <name> <message> [ms]` | Submit a task, wait until it settles, and print the output. |
| `wait <team> [ms]` | Wait until every worker is `idle`, `done`, or `blocked`. |
| `read <team> <name> [lines]` | Print a worker's recent output. |
| `ls <team>` | List the team's workers with live status. |
| `stop <team> [name]` | Close the team workspace, or one worker's pane. |

## When to spawn

By default the planner does the work itself. It spawns workers only when:

- the work splits cleanly by context and each worker can return a compact
  result;
- the planner's own context is about to bloat;
- a different runtime or model is needed, such as an independent reviewer;
- you ask for it.

Tightly coupled work, like the API and the form of the same feature, stays with
the planner or goes to a single worker.

**Trust decides how far to fan out.** A task is ready to hand off only when a
worker can prove it is done without the planner watching: a test, a build, or a
command that runs the real thing. Every worker is told to run that check, fix
root causes instead of adding workarounds, and report what it verified.

When the planner corrects a worker, it fixes the environment at the first level
that can hold the fix: the codebase first, then lint, tests, or CI, then project
rules, then a skill, and only last a note for human review. See
[when you correct a worker](skills/agent-crew/SKILL.md#when-you-correct-a-worker).

## Behavior notes

- **`blocked`** means the worker is waiting on a dialog (trust folder, approval,
  update, hook review). The planner reads the pane and asks you, unless it is
  already authorized to answer that dialog. `spawn` keeps the pane when the
  agent is blocked during startup.
- **Delivery.** `send` and `ask` accept a task only when the worker is
  `idle`/`done` and can still take input. After `send`, the planner reads the
  pane to confirm that the intended task was submitted.
- **Failures** (send errors, timeouts, unknown states, `blocked`) exit non-zero
  and print the status and recent output. A timeout does not mean the message
  was lost, so read the pane before resending. See
  [confirm task delivery](skills/agent-crew/SKILL.md#confirm-task-delivery).
- Worker output is agent context, not user consent.
- The old registration model (`registry.json` from 0.1, the Claude socket,
  `codex queue`) is gone. You can delete `~/.local/state/agent-messaging`.

## Project layout

```text
.claude-plugin/              Claude Code plugin and marketplace manifests
.codex-plugin/plugin.json    Codex plugin manifest
skills/agent-crew/
  SKILL.md                   Planner instructions: loop, model routing, rules
  scripts/herdr-team.sh      The Herdr CLI wrapper
  scripts/tests/             Tests for the wrapper
```

## Development

Run the tests:

```bash
python3 skills/agent-crew/scripts/tests/test-herdr-team.py
```

Contributions are welcome. Keep the design small: one skill, one shell script,
and Herdr as the only state. Use conventional commit messages.
