#!/bin/bash
watch -n 2 'echo "=== CONTAINER STATUS ===" && \
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.CPUPerc}}\t{{.MemUsage}}" && \
echo "" && \
echo "=== LATEST BLOCKS ===" && \
docker logs qbc-node 2>&1 | grep "Block.*mined" | tail -3'
