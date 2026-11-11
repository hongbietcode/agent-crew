<a id="readme-top"></a>

<div align="center">

<h1>Agent Crew</h1>

<p><strong>Run a team of coding agents from one session.</strong></p>

<p>
A planner spawns Claude, Codex and OpenCode workers in Herdr panes,<br>
picks the model for each task by cost, and verifies their results.
</p>

[![Stars][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]
[![Version][version-shield]][plugin-url]
[![Claude Code plugin][claude-shield]][install-url]
[![Codex plugin][codex-shield]][install-url]

<p>
<a href="#quick-start"><strong>Quick start</strong></a>
·
<a href="#model-routing">Model routing</a>
·
<a href="skills/agent-crew/SKILL.md">Planner guide</a>
·
<a href="https://github.com/hongbietcode/agent-crew/issues/new?labels=bug">Report bug</a>
·
<a href="https://github.com/hongbietcode/agent-crew/issues/new?labels=enhancement">Request feature</a>
</p>

</div>

<details>
<summary>Table of contents</summary>

1. [About the project](#about-the-project)
   - [Features](#features)
   - [How it works](#how-it-works)
2. [Getting started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
3. [Quick start](#quick-start)
4. [Model routing](#model-routing)
5. [Commands](#commands)
6. [When to spawn](#when-to-spawn)
7. [Behavior notes](#behavior-notes)
8. [Project layout](#project-layout)
9. [Contributing](#contributing)
10. [License](#license)

</details>

## About the project

Agent Crew turns your Claude Code or Codex session into a **planner**. The
planner splits your objective into tasks, starts **worker** agents in
[Herdr](https://herdr.dev) panes, hands each worker a task with the check that
proves it is done, waits for them, and reviews the real evidence (the diff and
the tests) before anything reaches you.

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
   │ demo-a      │      │ demo-scan   │      │ demo-cx     │
   │ Claude Opus │      │ Claude Haiku│      │ Codex Sol   │   Herdr panes,
   │ medium      │      │ xhigh       │      │ xhigh       │   2x2 grid per tab
   └─────────────┘      └─────────────┘      └─────────────┘
```

### Features

- **Parallel work without context bloat.** Independent tasks run side by side.
  Each worker keeps its own context, so the planner only receives compact
  results.
- **The right model for each task.** Mechanical work goes to a cheap model and
  hard work to a strong one. The defaults come from cost-per-task benchmarks,
  not from the price per token. See [Model routing](#model-routing).
- **Mixed runtimes.** Claude writes a fix and Codex reviews it independently.
  OpenCode or any other agent that Herdr can start works too.
- **Verified results.** Every task ships with the command that proves it is
  done. The planner reads `git diff` and runs the tests itself instead of
  trusting a worker's summary.
- **Mistakes don't recur.** When the planner corrects a worker, it also fixes
  the codebase, the checks, or the rules, so the next worker can't repeat the
  mistake.
- **Nothing hidden.** Herdr is the only state. A worker is a Herdr agent named
  `<team>-<name>`, so you can watch every pane, and `herdr agent list` is the
  team roster.

### How it works

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
   each its task. Delivery counts only once Herdr sees the worker start
   working.
3. **Wait**, **read**, and check the evidence: the diff and the tests. Reject
   workarounds and duplicated patterns even when the checks pass.
4. **Report** the combined result and **stop** the team.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting started

### Prerequisites

- [Herdr](https://herdr.dev) is running, and the planner sits in a Herdr pane
  (`HERDR_ENV=1`).
- The Herdr integration is installed for every agent you use as a worker.
  Check with `herdr integration status`; Herdr needs it to detect
  `idle`/`working`/`blocked`/`done`.
- `jq` (macOS ships `/usr/bin/jq`).

### Installation

Claude Code:

```text
/plugin install agent-crew --marketplace hongbietcode/agent-crew
```

Codex uses the `.codex-plugin/plugin.json` manifest:

```bash
codex plugin add agent-crew@personal
```

For local development:

```bash
git clone https://github.com/hongbietcode/agent-crew.git
claude --plugin-dir ./agent-crew
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Quick start

Ask the planner in plain language:

> Use agent-crew, team demo: audit the independent packages svc-a and svc-b in
> parallel, one worker per package; verify the findings and fix them yourself,
> then have a codex worker named cx independently review the fix.

Or drive the script directly:

```bash
T=./agent-crew/skills/agent-crew/scripts/herdr-team.sh

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Model routing

Price per token is misleading. What matters is the **cost per task**: a
stronger model often finishes in fewer tokens. The defaults below follow the
Artificial Analysis Intelligence Index, plotted as score against cost per task.

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

Opus `max` is avoided too: it costs about 1.7x `xhigh` for about 1.5 more
points.

### Codex workers

| Task | Model and effort | Args after `--` |
| --- | --- | --- |
| Mechanical, high-volume, easy to check | Terra 6.1 `low` | `-m gpt-6.1-terra -c model_reasoning_effort=low` |
| **Normal (default)** | **Sol 6.1 `medium`** | none |
| Hard task or independent review | Sol 6.1 `xhigh` | `-m gpt-6.1-sol -c model_reasoning_effort=xhigh` |
| Highest score regardless of cost | Astra `max` | `-m gpt-6-astra -c model_reasoning_effort=max` |

<details>
<summary>Intelligence Index v5.0 data (score · cost per task)</summary>

| Effort | Astra | Sol 6.1 | Terra 6.1 | Luna |
| --- | --- | --- | --- | --- |
| max | 57 · $6.24 | 55 · $1.27 | 51 · $0.96 | 28 · $0.15 |
| xhigh | 55 · $3.66 | 52 · $0.76 | 45 · $0.40 | 23 · $0.10 |
| high | 55 · $3.24 | 50 · $0.59 | 42 · $0.26 | 21 · $0.07 |
| medium | 51 · $2.73 | 46 · $0.36 | 38 · $0.17 | 18 · $0.04 |
| low | 43 · $1.42 | 35 · $0.16 | 29 · $0.07 | 10 · $0.01 |

</details>

What the data shows:

- Luna above `low` loses to Terra `low`, which scores higher at similar or
  lower cost.
- Sol `max` matches Astra `high` for about 40% of the cost, and Astra below
  `max` loses to Sol everywhere.
- On the Coding Agent Index (Codex harness), Sol `medium` scores 61.4 at $0.70
  while Sol `max` scores 60.1 at $1.55, so `max` is skipped. Sol `xhigh` (62.9
  at $1.04) is the value peak for hard coding work.

> [!NOTE]
> Benchmarks move. Figures come from Artificial Analysis via
> [Respan](https://www.respan.ai/articles/gpt-6-sol-vs-luna-vs-astra) (Codex,
> Nov 2026), [Preuve](https://preuve.ai/blog/ai-coding-models-statistics-2026)
> (Coding Agent Index, Oct 2026), and a Respan chart for Claude (Sep 2026).
> Compare numbers only within one table, since index versions differ. Override
> any default per worker with native args after `--`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Project layout

```text
.claude-plugin/              Claude Code plugin and marketplace manifests
.codex-plugin/plugin.json    Codex plugin manifest
skills/agent-crew/
  SKILL.md                   Planner instructions: loop, model routing, rules
  scripts/herdr-team.sh      The Herdr CLI wrapper
  scripts/tests/             Tests for the wrapper
```

## Contributing

Contributions are welcome. Keep the design small: one skill, one shell script,
and Herdr as the only state.

1. Fork the project.
2. Create a branch: `git checkout -b feat/my-change`.
3. Run the tests: `python3 skills/agent-crew/scripts/tests/test-herdr-team.py`.
4. Commit with a conventional message: `git commit -m "feat: add my change"`.
5. Push the branch and open a pull request.

Found a bug or have an idea? [Open an issue](https://github.com/hongbietcode/agent-crew/issues).

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- Badge links -->
[stars-shield]: https://img.shields.io/github/stars/hongbietcode/agent-crew?style=flat-square
[stars-url]: https://github.com/hongbietcode/agent-crew/stargazers
[issues-shield]: https://img.shields.io/github/issues/hongbietcode/agent-crew?style=flat-square
[issues-url]: https://github.com/hongbietcode/agent-crew/issues
[license-shield]: https://img.shields.io/github/license/hongbietcode/agent-crew?style=flat-square
[license-url]: LICENSE
[version-shield]: https://img.shields.io/badge/version-0.5.1-blue?style=flat-square
[plugin-url]: .claude-plugin/plugin.json
[claude-shield]: https://img.shields.io/badge/Claude_Code-plugin-D97757?style=flat-square
[codex-shield]: https://img.shields.io/badge/Codex-plugin-412991?style=flat-square
[install-url]: #installation
