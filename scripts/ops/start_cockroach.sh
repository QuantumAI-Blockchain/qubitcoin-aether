#!/bin/bash
cockroach start-single-node \
  --certs-dir=/home/ash/qubitcoin/data/certs \
  --listen-addr=localhost:26257 \
  --http-addr=localhost:8081 \
  --store=/home/ash/qubitcoin/data/cockroach
