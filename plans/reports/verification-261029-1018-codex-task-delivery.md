# Codex task delivery verification

Date: 2026-10-29, Asia/Saigon. Source: agent-messaging 0.4.2.

## Outcome and boundary

Task submission uses Herdr's native text-plus-Enter operation. `send` accepts
only ready idle/done workers, returns success only for observed `working`,
and preserves submission failures. `ask` retains its single native activity
and completion wait. Both diagnose ambiguous results without sending extra
input. The planner must read the pane to confirm the intended task before
reporting assignment. Missing Enter recovery requires the entire intended
task in an idle normal composer with no dialog, followed by one Enter and
receipt verification.

This change introduces no daemon, queue, task registry, automatic resend, or
automatic dialog response. The existing workspace and model selection remain.

## Reproduced cause

The original POSIX shell pipeline ignored Herdr's failure when `jq` succeeded.
A controlled failing prompt produced `{"started":"demo-cx","status":null}`
and exit 0. A `blocked` response also received a `started` label. The original
skill described immediate submission and did not require a receipt read.

Installed CLI help and the [Herdr automation documentation](https://herdr.dev/docs/agent-automation/)
confirm that `agent prompt` sends text and Enter together. Its activity gate
does not identify individual turns when the target is already working;
the helper therefore rejects new submissions to a busy worker.

## Checks

- Regression suite: `python3 skills/agent-messaging/scripts/tests/test-herdr-team.py -v`.
  The original script failed 34 expectations across nine methods; the first
  candidate passed all 34. Cases exercise real `/bin/sh` and `jq` with a
  logged, temporary Herdr boundary executable. No real agents receive input.
  Review added four preflight-error cases that failed before the correction;
  the final suite passed all 38 cases across ten methods in 5.77 seconds.
- Shell syntax: `/bin/sh -n skills/agent-messaging/scripts/herdr-team.sh` passed.
- Skill structure validator passed. Prompt lint reported zero high, medium,
  or low findings.
- Both plugin manifests parse and declare 0.4.2. README's new delivery link
  resolves to the existing skill heading. `git diff --check` passed.
- `claude plugin validate . --strict` reported validation passed. Its separate
  plugin-directory checks identified the existing missing license and OS
  metadata files, plus an absent icon; directory publication is not validated.

## Consumer comparison

Two fresh subagents consumed only the original or candidate instructions and
answered the same five scenarios without executing live commands. These were
forced-load, single-run probes, not routing or reliability benchmarks.

| Scenario | Original consumer artifact | Candidate consumer artifact |
| --- | --- | --- |
| Idle Codex, then independent work | Issued `send`, then moved to the next worker without an immediate receipt read. | Required `started`/`working`, then `read` before moving on. |
| Stalled send with null status | Kept delivery unconfirmed and read the pane, but found no defined recovery. | Inspected input and state; allowed one Enter only after verifying all composer conditions. |
| Worker busy on earlier task | Waited and read before sending again. | Preserved that behavior and required readiness before the new assignment. |
| `blocked` response | Treated delivery as unconfirmed and inspected the dialog. | Preserved that distinction and reused only applicable existing authorization. |
| Complete task visibly pending, idle, no dialog | Interpreted the old key rule as requiring additional confirmation. | Issued one `send-keys ... enter`, waited for `working`, then read receipt evidence. |

Original instructions: [snapshot](skill-261029-1018-delivery-original.txt),
SHA-256 `a8add951e1adfb4c043850ee071e8c1c7db59f04c01239298b1ec502328497d3`.
Candidate skill SHA-256:
`35d8da12be351077a2cc4b61aacc5f6b48e40810ed635b3ccb8f374b5eef7cdc`.
Consumer sessions: `/root/baseline_consumer`, `/root/candidate_consumer`.
Exact effective model IDs, token counts, and elapsed costs were not exposed.

## Review and limits

An independent reviewer verified status validation, shell error propagation,
timeout semantics, documentation alignment, and conditional Enter recovery.
It identified one additional preflight-error diagnostics gap for correction.
The gap was fixed with a failing-then-passing regression that also checks
that a diagnostic failure cannot replace the original exit code.
Focused independent re-review confirmed the correction with no remaining
concrete concern.

The current shell is outside `HERDR_ENV=1`; no live Codex round trip was run.
The physical missing-Enter symptom remains unverified against a live worker.
Only repository source and version metadata were changed; installed plugin
caches were not updated. Preflight and submission are separate CLI calls,
so the planner still owns exclusive dispatch to each worker.
