#!/bin/bash
# Start 3 QBC nodes locally for P2P network testing
# Each node mines independently and syncs via P2P

set -e

echo "🚀 Starting Multi-Node QBC P2P Network"
echo "========================================="
echo ""

# Configuration
BASE_DIR="/home/ash/qubitcoin"
LOG_DIR="$BASE_DIR/logs"
SRC_DIR="$BASE_DIR/src"

# Kill any existing nodes
echo "Cleaning up existing nodes..."
pkill -f "python3.*run_node.py" 2>/dev/null || true
sleep 2

# Create logs directory
mkdir -p "$LOG_DIR"

# Clean old logs
rm -f "$LOG_DIR"/node*.log 2>/dev/null || true

echo ""
echo "Starting 3 QBC nodes..."
echo ""

# ============================================================================
# NODE 1 - Bootstrap Node
# ============================================================================
echo "📡 Starting Node 1 (Bootstrap)..."
cd "$SRC_DIR"

# Export environment for Node 1
export P2P_PORT=6001
export RPC_PORT=5000
export NODE_NAME="bootstrap-1"
unset PEER_SEEDS  # Bootstrap node has no seeds

# Start Node 1 in background
nohup python3 run_node.py > "$LOG_DIR/node1.log" 2>&1 &
NODE1_PID=$!

echo "   ✓ Node 1: P2P=6001, RPC=5000, PID=$NODE1_PID"
echo "   📝 Logs: $LOG_DIR/node1.log"

# Wait for Node 1 to start
sleep 8

# ============================================================================
# NODE 2 - Validator
# ============================================================================
echo ""
echo "📡 Starting Node 2 (Validator)..."
cd "$SRC_DIR"

# Export environment for Node 2
export P2P_PORT=6002
export RPC_PORT=5001
export NODE_NAME="validator-1"
export PEER_SEEDS="localhost:6001"

# Start Node 2 in background
nohup python3 run_node.py > "$LOG_DIR/node2.log" 2>&1 &
NODE2_PID=$!

echo "   ✓ Node 2: P2P=6002, RPC=5001, PID=$NODE2_PID"
echo "   📝 Logs: $LOG_DIR/node2.log"
echo "   🔗 Connecting to: localhost:6001"

# Wait for Node 2 to start
sleep 8

# ============================================================================
# NODE 3 - Validator
# ============================================================================
echo ""
echo "📡 Starting Node 3 (Validator)..."
cd "$SRC_DIR"

# Export environment for Node 3
export P2P_PORT=6003
export RPC_PORT=5002
export NODE_NAME="validator-2"
export PEER_SEEDS="localhost:6001,localhost:6002"

# Start Node 3 in background
nohup python3 run_node.py > "$LOG_DIR/node3.log" 2>&1 &
NODE3_PID=$!

echo "   ✓ Node 3: P2P=6003, RPC=5002, PID=$NODE3_PID"
echo "   📝 Logs: $LOG_DIR/node3.log"
echo "   🔗 Connecting to: localhost:6001,localhost:6002"

echo ""
echo "========================================="
echo "✅ Multi-Node Network Started!"
echo "========================================="
echo ""
echo "Node Information:"
echo "  Node 1 (Bootstrap): http://localhost:5000  [P2P: 6001]"
echo "  Node 2 (Validator): http://localhost:5001  [P2P: 6002]"
echo "  Node 3 (Validator): http://localhost:5002  [P2P: 6003]"
echo ""
echo "PIDs: $NODE1_PID, $NODE2_PID, $NODE3_PID"
echo ""
echo "View Logs:"
echo "  tail -f $LOG_DIR/node1.log"
echo "  tail -f $LOG_DIR/node2.log"
echo "  tail -f $LOG_DIR/node3.log"
echo ""
echo "Quick Commands:"
echo "  ./scripts/test_network.sh     - Test P2P connectivity"
echo "  ./scripts/stop_multi_node.sh  - Stop all nodes"
echo ""
echo "Wait ~30 seconds, then run: ./scripts/test_network.sh"
echo ""
