#!/bin/bash
# Test QBC Multi-Node P2P Network
# Checks connectivity, peers, and blockchain sync

set -e

echo "🔍 Testing QBC Multi-Node P2P Network"
echo "========================================="
echo ""

# Check if jq is available for JSON parsing
if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not found, installing..."
    sudo apt-get update -qq && sudo apt-get install -y jq
fi

# Function to test a node
test_node() {
    local port=$1
    local name=$2
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📡 $name (RPC: $port)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if node is responding
    if ! curl -s -f http://localhost:$port/ > /dev/null 2>&1; then
        echo "   ❌ Node not responding on port $port"
        echo ""
        return 1
    fi
    
    # Get node info
    local response=$(curl -s http://localhost:$port/ 2>/dev/null)
    
    # Parse response
    local height=$(echo "$response" | jq -r '.height // "N/A"')
    local version=$(echo "$response" | jq -r '.version // "N/A"')
    local peers=$(echo "$response" | jq -r '.p2p.peers // "N/A"')
    local p2p_port=$(echo "$response" | jq -r '.p2p.port // "N/A"')
    
    echo "   Version:    $version"
    echo "   Height:     $height"
    echo "   P2P Port:   $p2p_port"
    echo "   Peers:      $peers"
    
    # Get P2P peer details
    local p2p_response=$(curl -s http://localhost:$port/p2p/peers 2>/dev/null)
    
    if [ ! -z "$p2p_response" ]; then
        local peer_count=$(echo "$p2p_response" | jq -r '.peer_count // 0')
        echo "   Peer Count: $peer_count"
        
        # List peers
        if [ "$peer_count" -gt 0 ]; then
            echo ""
            echo "   Connected Peers:"
            echo "$p2p_response" | jq -r '.peers[] | "     • \(.peer_id) (\(.host):\(.port)) - Score: \(.score)"' 2>/dev/null || echo "     (peer details unavailable)"
        fi
    fi
    
    # Get P2P stats
    local stats_response=$(curl -s http://localhost:$port/p2p/stats 2>/dev/null)
    
    if [ ! -z "$stats_response" ]; then
        local msgs_sent=$(echo "$stats_response" | jq -r '.messages.sent // 0')
        local msgs_recv=$(echo "$stats_response" | jq -r '.messages.received // 0')
        local blocks_prop=$(echo "$stats_response" | jq -r '.messages.blocks_propagated // 0')
        
        echo ""
        echo "   P2P Stats:"
        echo "     Messages Sent:      $msgs_sent"
        echo "     Messages Received:  $msgs_recv"
        echo "     Blocks Propagated:  $blocks_prop"
    fi
    
    echo ""
    
    # Return height for sync check
    echo "$height"
}

# Test each node
echo "Testing individual nodes..."
echo ""

height1=$(test_node 5000 "Node 1 (Bootstrap)")
height2=$(test_node 5001 "Node 2 (Validator)")
height3=$(test_node 5002 "Node 3 (Validator)")

# Check sync status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Blockchain Sync Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   Node 1 Height: $height1"
echo "   Node 2 Height: $height2"
echo "   Node 3 Height: $height3"
echo ""

# Clean up non-numeric heights
height1_clean="${height1//[^0-9]/}"
height2_clean="${height2//[^0-9]/}"
height3_clean="${height3//[^0-9]/}"

# Check if all heights are the same
if [ "$height1_clean" = "$height2_clean" ] && [ "$height2_clean" = "$height3_clean" ] && [ ! -z "$height1_clean" ]; then
    echo "   ✅ ALL NODES SYNCED at height $height1"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ P2P Network Operating Correctly!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    exit 0
else
    echo "   ⚠️  NODES NOT FULLY SYNCED"
    echo "      This is normal if nodes just started."
    echo "      Wait 30 seconds and test again."
    echo ""
    
    # Calculate max difference
    max_h=$height1_clean
    min_h=$height1_clean
    
    for h in $height2_clean $height3_clean; do
        [ ! -z "$h" ] && [ "$h" -gt "$max_h" ] && max_h=$h
        [ ! -z "$h" ] && [ "$h" -lt "$min_h" ] && min_h=$h
    done
    
    diff=$((max_h - min_h))
    
    echo "   Height difference: $diff blocks"
    
    if [ "$diff" -lt 5 ]; then
        echo "   ✓ Nodes are close (difference < 5 blocks)"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ P2P Network Operating (syncing...)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        exit 0
    else
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠️  P2P Network May Have Issues"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check logs: tail -f logs/node*.log"
        echo "  2. Verify P2P connections: curl http://localhost:5000/p2p/peers"
        echo "  3. Wait longer (nodes may still be syncing)"
        echo ""
        exit 1
    fi
fi
