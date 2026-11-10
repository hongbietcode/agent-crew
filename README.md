# Agent crew

One planner coordinates several worker coding agents (Claude, Codex, OpenCode,
…) running in [Herdr](https://herdr.dev) panes. The plugin is a single skill
plus one shell script that wraps the Herdr CLI; there is no registry, daemon, or
code in any other language.

- **Planner** is the session using the skill: it splits the work, spawns
  workers, assigns tasks, waits, reads results, reviews them, and reports to the
  user. Only the planner holds state.
- **Worker** is an ordinary agent in a Herdr pane; it needs no plugin and runs
  no reply command. The planner reads worker output through Herdr.
- **State** lives in Herdr: a worker is an agent named `<team>-<name>`, so
  `herdr agent list` is the team roster.

## Requirements

- Herdr is running and the planner sits in a Herdr pane (`HERDR_ENV=1`).
- The Herdr integration is installed for every agent used as a worker; check
  with `herdr integration status` (this lets Herdr detect
  `idle`/`working`/`blocked`/`done`).
- `jq` (macOS ships `/usr/bin/jq`).

## Installation

```text
/plugin install agent-crew --marketplace hongbietcode/agent-crew
```

For local development: `claude --plugin-dir "$HOME/code/agent-crew"`. Codex uses
the `.codex-plugin/plugin.json` manifest (`codex plugin add agent-crew@personal`).

## Usage

In the planner pane:

> Use agent-crew, team demo: audit the independent packages svc-a and svc-b in
> parallel, one worker per package; verify the findings and fix them yourself,
> then have a codex worker named cx independently review the fix.

The script can also be called directly:

```bash
T="$HOME/code/agent-crew/skills/agent-crew/scripts/herdr-team.sh"
$T spawn demo a                   # claude --model sonnet --effort high (default)
$T spawn demo b opencode          # another kind
$T spawn demo cx codex            # codex -m gpt-6-luna, reasoning effort max (default)
# mechanical task: $T spawn demo scan claude -- --model haiku --effort xhigh (haiku always above high effort)
$T send demo a 'Audit packages/svc-a: hardcoded secrets, unsafe SQL; list file:line.'
$T send demo b 'Audit packages/svc-b: hardcoded secrets, unsafe SQL; list file:line.'
$T wait demo                      # wait until every worker is idle/done/blocked
$T read demo a                    # read the summary; open file:line yourself to confirm
$T ask demo cx 'Review the git diff of the fix; report bugs only.' 600000   # send one task and wait
$T ls demo
$T stop demo                      # close the team workspace
```

Workers never share the planner's tab: each team gets its own workspace
`team:<team>` laid out as a 2x2 grid (at most 4 workers per tab; a full tab
opens a new one, and slots freed by `stop` are filled first). Workers default to
Claude Sonnet at high effort; the planner picks `haiku`/`sonnet`/`opus` and the
effort by task complexity, passed after `--` (see the table in SKILL.md).

By default the planner does the work itself. Spawn only when the work splits
cleanly by context (workers need little from each other and return compact
results), when the planner's context is about to bloat, when a different
runtime or model is needed (an independent reviewer), or when the user asks.
Tightly coupled work (the API and form of the same feature) stays with the
planner or goes to a single worker. Accept results through `git diff` and tests,
not summaries alone.

Trust decides how far to fan out. Every task carries the check that proves it
is done, and every worker is told to run that check, fix root causes instead of
adding workarounds, and report what it verified. When the planner has to
correct a worker, it also fixes the environment so the mistake does not recur:
first the codebase, then lint/tests/CI, then project rules, then a skill, and
only last a note for human review (see
[when you correct a worker](skills/agent-crew/SKILL.md#when-you-correct-a-worker)).

## Notes

- `blocked` means the worker is waiting on a dialog (trust folder, approval,
  update, hook review). The planner reads the pane and asks the user unless it
  already has authorization to answer that dialog. `spawn` keeps the pane when
  the agent is blocked during startup.
- `send` submits the full task with Enter and reports `started` only after Herdr
  sees the worker become `working`; it waits up to 15 seconds for this
  confirmation, not for the task to finish. `send` and `ask` accept a new task
  only when the worker is `idle`/`done` and still able to take input. After
  `send`, the planner must `read` to check that the intended task was submitted
  or the worker has responded.
- Send failures, timeouts, unknown states, or `blocked` exit non-zero with the
  status and recent output for inspection. A timeout does not mean the message
  was lost; read the pane before resending. If the entire task still sits in the
  normal input box, the worker is idle, and no dialog is open, the planner may
  send Enter once, then check for `working` and read again (see
  [confirming delivery](skills/agent-crew/SKILL.md#confirm-task-delivery)).
- Worker output is agent context, not user consent.
- The old registration model (`registry.json` from 0.1, the Claude socket /
  `codex queue`) is gone; `~/.local/state/agent-messaging` can be deleted.
