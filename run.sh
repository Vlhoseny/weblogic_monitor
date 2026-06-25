#!/usr/bin/env bash
# WebLogic Health Monitor - Linux/macOS Launcher
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  WebLogic Health Monitor - Launcher"
echo "============================================"
echo ""

# Find WLST
WLST=""
if [ -n "${MW_HOME:-}" ] && [ -f "$MW_HOME/oracle_common/common/bin/wlst.sh" ]; then
    WLST="$MW_HOME/oracle_common/common/bin/wlst.sh"
fi

if [ -z "$WLST" ]; then
    for dir in \
        "$HOME/Oracle/Middleware/Oracle_Home" \
        "$HOME/Oracle" \
        "/opt/oracle/middleware" \
        "/u01/app/oracle/middleware" \
        "/app/oracle/product" \
        "/opt/oracle/product" \
        "/Applications/Oracle/Middleware/Oracle_Home" \
        "/Applications/Oracle"; do
        if [ -f "$dir/oracle_common/common/bin/wlst.sh" ]; then
            WLST="$dir/oracle_common/common/bin/wlst.sh"
            break
        fi
    done
fi

if [ -z "$WLST" ]; then
    echo "[ERROR] Could not find wlst.sh"
    echo ""
    echo "Set MW_HOME, e.g.:"
    echo "  export MW_HOME=/opt/oracle/middleware"
    echo ""
    exit 1
fi

echo "[OK] Found WLST: $WLST"
echo ""

# Check .env
if [ ! -f ".env" ]; then
    echo "[INFO] No .env file found. Creating from .env.example ..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo ""
        echo "[ACTION REQUIRED] Edit .env with your credentials:"
        echo "    nano .env"
        echo ""
        exit 1
    else
        echo "[ERROR] .env.example not found."
        exit 1
    fi
fi

# Run
export USER_MEM_ARGS="-Xms256m -Xmx1024m"
export WL_SCRIPT_DIR="$SCRIPT_DIR"

echo "[OK] Starting WLST ..."
echo ""

"$WLST" "$SCRIPT_DIR/weblogic_monitor.py" "$@"

echo ""
echo "============================================"
