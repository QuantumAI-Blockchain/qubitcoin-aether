#!/bin/bash
# Stop all QBC nodes

echo "🛑 Stopping Multi-Node QBC Network"
echo "===================================="
echo ""

# Kill all run_node.py processes
echo "Stopping all QBC node processes..."
pkill -f "python3.*run_node.py" 2>/dev/null || true

# Wait for processes to terminate
sleep 2

# Check if any are still running
if pgrep -f "python3.*run_node.py" > /dev/null; then
    echo "⚠️  Some processes still running, force killing..."
    pkill -9 -f "python3.*run_node.py" 2>/dev/null || true
    sleep 1
fi

# Verify all stopped
if pgrep -f "python3.*run_node.py" > /dev/null; then
    echo "❌ Failed to stop all nodes"
    echo ""
    echo "Remaining processes:"
    ps aux | grep "python3.*run_node.py" | grep -v grep
    exit 1
else
    echo "✅ All QBC nodes stopped"
fi

echo ""
echo "To restart: ./scripts/start_multi_node.sh"
echo ""
