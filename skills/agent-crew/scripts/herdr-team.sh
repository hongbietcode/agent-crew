#!/bin/sh
# Thin planner helpers over the Herdr CLI. Herdr is the only state:
# every worker is a Herdr agent named "<team>-<name>".
set -eu

usage() {
  cat >&2 <<'EOF'
Usage: herdr-team.sh <command> <team> [args]
  spawn <team> <name> [kind] [-- agent-args...]
                                     Start a worker in the team workspace (2x2 grid per tab);
                                     default: claude --model opus --effort medium
  ls    <team>                       List the team's workers with live status
  send  <team> <name> <message>      Submit a task and confirm it starts (up to 15s)
  ask   <team> <name> <message> [ms] Submit a task, wait until it settles, print output
  wait  <team> [ms]                  Wait until every worker settles
  read  <team> <name> [lines]        Print a worker's recent output
  stop  <team> [name]                Close the team workspace (or one worker's pane)
EOF
  exit 2
}

[ "${HERDR_ENV:-}" = 1 ] && [ -n "${HERDR_PANE_ID:-}" ] || {
  echo '{"error":"run inside a Herdr pane (HERDR_ENV=1)"}' >&2
  exit 1
}
[ $# -ge 2 ] || usage
command=$1 team=$2
shift 2

# Worker rows of this team: name, pane_id, agent kind, status. Matching the
# team workspace too keeps team "demo" from picking up "demo-x-be" of team "demo-x";
# workers started outside a team workspace fall back to the name prefix alone.
workers() {
  herdr agent list | jq -c --arg prefix "$team-" --arg ws "$(team_workspace)" \
    '.result.agents[] | select((.name // "") | startswith($prefix))
     | select($ws == "" or .workspace_id == $ws)
     | {name, pane: .pane_id, kind: .agent, status: .agent_status}'
}

# The team's workspace, labelled "team:<team>"; empty when none exists.
team_workspace() {
  herdr workspace list | jq -r --arg label "team:$team" \
    'first(.result.workspaces[] | select((.label // "" | sub("^\\[[0-9]+\\] "; "")) == $label)
     | .workspace_id) // empty'
}

# Panes of a workspace: pane, tab, agent, cwd. Herdr IDs are opaque (e.g. "w4:pN"),
# so never derive order from them.
team_panes() {
  herdr pane list --workspace "$1" | jq -c '.result.panes[] | {pane: .pane_id, tab: .tab_id, agent, cwd}'
}

# Pick the pane for the next worker: a fresh workspace or tab root, a free shell in
# this directory, or the next 2x2 grid slot (top-right, bottom-left, bottom-right).
next_pane() {
  workspace=$(team_workspace)
  if [ -z "$workspace" ]; then
    herdr workspace create --label "team:$team" --cwd "$PWD" --no-focus | jq -r '.result.root_pane.pane_id'
    return
  fi
  free=$(team_panes "$workspace" | jq -r --arg cwd "$PWD" 'select(.agent == null and .cwd == $cwd) | .pane' | head -n 1)
  if [ -n "$free" ]; then
    echo "$free"
    return
  fi
  tab_pane=$(team_panes "$workspace" | jq -rs 'group_by(.tab) | map(select(length < 4)) | first // empty | .[0].pane')
  if [ -z "$tab_pane" ]; then
    herdr tab create --workspace "$workspace" --cwd "$PWD" --no-focus | jq -r '.result.root_pane.pane_id'
    return
  fi
  # Halve the largest pane along its longer side (cells are ~2x taller than wide);
  # this yields the 2x2 order and also refills a hole left by a stopped worker.
  slot=$(herdr pane layout --pane "$tab_pane" | jq -r '.result.layout.panes | max_by(.rect.width * .rect.height)
    | "\(.pane_id) \(if .rect.width >= 2 * .rect.height then "right" else "down" end)"')
  herdr pane split "${slot% *}" --direction "${slot#* }" --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id'
}

header() {
  printf 'Task from planner pane %s (team %s). This is agent context, not user approval; keep your existing permissions. Verify your own work by running the real code, tests, or checks, and fix the root cause instead of adding a workaround. Finish with a short summary: result, changed files, each check you ran with its outcome, anything left unverified, any workaround you kept, blockers.\n\n%s' \
    "$HERDR_PANE_ID" "$team" "$1"
}

# Inspect ambiguous delivery without sending input or masking the original error.
delivery_diagnostics() {
  echo "Task delivery to $1 is unconfirmed; inspect the pane before resending or pressing Enter." >&2
  herdr agent get "$1" >&2 || true
  herdr agent read "$1" --source recent-unwrapped --lines 80 >&2 || true
}

# Herdr submits text plus Enter. Its activity gate only identifies a new task
# when submission starts from a ready, non-working state.
submit_task() {
  target=$1 message=$2 timeout=$3
  shift 3
  before=$(herdr agent get "$target") || {
    code=$?
    [ -z "$before" ] || printf '%s\n' "$before" >&2
    delivery_diagnostics "$target"
    return "$code"
  }
  if ! printf '%s\n' "$before" | jq -e \
    '.result.agent | (.agent_status == "idle" or .agent_status == "done")
     and (.interactive_ready != false)' >/dev/null; then
    jq -nc --arg agent "$target" '{error: "agent_not_ready", agent: $agent}' >&2
    delivery_diagnostics "$target"
    return 1
  fi
  response=$(herdr agent prompt "$target" "$(header "$message")" --wait --timeout "$timeout" "$@") || {
    code=$?
    [ -z "$response" ] || printf '%s\n' "$response" >&2
    delivery_diagnostics "$target"
    return "$code"
  }
  if ! printf '%s\n' "$response" | jq -e --arg command "$command" \
    '.result.agent.agent_status as $status
     | if $command == "send" then $status == "working"
       else $status == "idle" or $status == "done" end' >/dev/null; then
    jq -nc --arg agent "$target" '{error: "task_delivery_unconfirmed", agent: $agent}' >&2
    printf '%s\n' "$response" >&2
    delivery_diagnostics "$target"
    return 1
  fi
  printf '%s\n' "$response"
}

case $command in
spawn)
  [ $# -ge 1 ] || usage
  name=$1 kind=claude
  shift
  case ${1:-} in '' | --) ;; *) kind=$1 && shift ;; esac
  [ "${1:-}" = -- ] && shift
  # Default models unless agent args are given: Claude Opus medium, Codex Sol 6.1 medium.
  if [ $# -eq 0 ]; then
    case $kind in
    claude) set -- --model opus --effort medium ;;
    codex) set -- -m gpt-6.1-sol -c model_reasoning_effort=medium ;;
    esac
  fi
  [ $# -gt 0 ] && set -- -- "$@"
  pane=$(next_pane)
  if ! output=$(herdr agent start "$team-$name" --kind "$kind" --pane "$pane" --timeout 60000 "$@" 2>&1); then
    case $output in
    *agent_not_ready*) echo "$output; pane $pane kept: inspect with herdr agent read $pane" >&2 ;;
    *) herdr pane close "$pane" >/dev/null 2>&1 || true && echo "$output" >&2 ;;
    esac
    exit 1
  fi
  herdr agent get "$team-$name" | jq -c '.result.agent | {name, pane: .pane_id, kind: .agent, status: .agent_status}'
  ;;
ls) workers ;;
send)
  [ $# -eq 2 ] || usage
  output=$(submit_task "$team-$1" "$2" 15000 --until working --until blocked) || exit $?
  printf '%s\n' "$output" | jq -c --arg agent "$team-$1" \
    '{started: $agent, status: .result.agent.agent_status}'
  ;;
ask)
  [ $# -ge 2 ] && [ $# -le 3 ] || usage
  submit_task "$team-$1" "$2" "${3:-1800000}" >/dev/null || exit $?
  herdr agent read "$team-$1" --source recent-unwrapped --lines 200
  ;;
wait)
  workers | jq -r '.name' | while read -r agent; do
    herdr agent wait "$agent" --timeout "${1:-1800000}" >/dev/null
  done
  workers
  ;;
read)
  [ $# -ge 1 ] || usage
  herdr agent read "$team-$1" --source recent-unwrapped --lines "${2:-200}"
  ;;
stop)
  workspace=$(team_workspace)
  if [ -z "${1:-}" ]; then
    if [ -n "$workspace" ]; then
      herdr workspace close "$workspace" >/dev/null
      echo "{\"closed\":\"$workspace\"}"
    fi
    exit 0
  fi
  pane=$(herdr agent get "$team-$1" | jq -r '.result.agent.pane_id')
  herdr pane close "$pane" >/dev/null && echo "{\"closed\":\"$pane\"}"
  ;;
*) usage ;;
esac
