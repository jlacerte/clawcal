#!/usr/bin/env bash
set -euo pipefail

LABEL="com.clawcal.server"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SRC_PLIST="$(cd "$(dirname "$0")" && pwd)/com.clawcal.server.plist"
LOG_DIR="$HOME/.clawcal"
PORT=8100

_ensure_log_dir() { mkdir -p "$LOG_DIR"; }

cmd_install() {
    _ensure_log_dir
    cp "$SRC_PLIST" "$PLIST"
    echo "Installed $PLIST"
    launchctl load "$PLIST"
    echo "Service loaded and started."
    sleep 2
    cmd_status
}

cmd_start() {
    if [ ! -f "$PLIST" ]; then
        echo "Not installed. Run: ./clawcal.sh install"
        exit 1
    fi
    launchctl load "$PLIST" 2>/dev/null || true
    launchctl start "$LABEL"
    echo "Started $LABEL"
    sleep 1
    cmd_status
}

cmd_stop() {
    launchctl stop "$LABEL" 2>/dev/null || true
    echo "Stopped $LABEL"
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_uninstall() {
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Uninstalled $LABEL"
}

cmd_status() {
    echo "=== launchd ==="
    launchctl list "$LABEL" 2>/dev/null || echo "Not loaded"
    echo ""
    echo "=== health ==="
    curl -sf "http://127.0.0.1:$PORT/health" 2>/dev/null | python3 -m json.tool || echo "Not responding on port $PORT"
}

cmd_logs() {
    echo "=== stdout (last 30) ==="
    tail -30 "$LOG_DIR/server.log" 2>/dev/null || echo "(no log)"
    echo ""
    echo "=== stderr (last 30) ==="
    tail -30 "$LOG_DIR/server.err.log" 2>/dev/null || echo "(no log)"
}

cmd_tail() {
    tail -f "$LOG_DIR/server.log" "$LOG_DIR/server.err.log"
}

case "${1:-help}" in
    install)   cmd_install ;;
    start)     cmd_start ;;
    stop)      cmd_stop ;;
    restart)   cmd_restart ;;
    uninstall) cmd_uninstall ;;
    status)    cmd_status ;;
    logs)      cmd_logs ;;
    tail)      cmd_tail ;;
    help|*)
        echo "Usage: clawcal.sh {install|start|stop|restart|uninstall|status|logs|tail}"
        ;;
esac
