#!/bin/bash
# Install, remove or inspect the Monday morning refresh.
#
#   ./install-cron.sh install     load the launchd job (Monday 09:00)
#   ./install-cron.sh uninstall   unload and delete it
#   ./install-cron.sh status      is it loaded, when did it last run
#   ./install-cron.sh run-now     run the job immediately, same as launchd would
#
# launchd rather than crontab on purpose: if the Mac is asleep at 09:00, launchd runs the
# job on wake, which is what "when you start work" actually means. cron would just skip it.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="local.review-triage"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$REPO/launchd/$LABEL.plist.template"

case "${1:-status}" in
  install)
    for tool in gh python3; do
      command -v "$tool" >/dev/null || { echo "FAIL $tool not on PATH"; exit 1; }
    done
    # Pin the directories of the tools this shell resolves, since launchd will not search.
    JOB_PATH="$(dirname "$(command -v gh)"):$(dirname "$(command -v python3)"):/usr/bin:/bin:/usr/sbin:/sbin"
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.claude/triage"
    sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" -e "s|__PATH__|$JOB_PATH|g" \
      "$TEMPLATE" > "$PLIST"
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "installed  $PLIST"
    echo "schedule   Monday 09:00 (runs on wake if the machine was asleep)"
    echo "log        $HOME/.claude/triage/cron.log"
    ;;
  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "removed    $PLIST"
    ;;
  run-now)
    launchctl kickstart -p "gui/$(id -u)/$LABEL" 2>/dev/null \
      || { echo "job not loaded, running the script directly"; "$REPO/bin/review-triage-cron"; }
    sleep 8
    tail -6 "$HOME/.claude/triage/cron.log" 2>/dev/null || echo "no log yet"
    ;;
  status)
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "loaded     $LABEL"
      launchctl print "gui/$(id -u)/$LABEL" \
        | grep -E "state|last exit code|runs =" | sed 's/^[[:space:]]*/           /'
    else
      echo "not loaded (run: ./install-cron.sh install)"
    fi
    echo "last runs:"
    tail -6 "$HOME/.claude/triage/cron.log" 2>/dev/null | sed 's/^/           /' \
      || echo "           no log yet"
    ;;
  *)
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    ;;
esac
