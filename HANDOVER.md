# QUBITCOIN PROJECT HANDOVER

## CURRENT STATUS (2026-01-31)

### ✅ WORKING COMPONENTS
- CockroachDB: Running on ports 30000 (SQL) + 30001 (Web UI) with SSL
- Qubitcoin Node: Mining operational, 2515+ blocks mined
- IPFS: Running on port 5002 (API) + 8082 (Gateway)
- Database: 38,420+ QBC minted, 29 tables
- Quantum VQE: Working, mining at ~1.76s/block
- RPC API: Port 5000 active

### ⚠️ CRITICAL - PORT CHANGED!
**Database moved from port 26257 → 30000**

Files that need updating:
1. /home/ash/qubitcoin/.env
2. /home/ash/qubitcoin/src/qubitcoin/config.py

Change all instances of `localhost:26257` to `localhost:30000`

### 🎯 IMMEDIATE TASKS
1. Update database port in .env and config.py
2. Initialize stablecoin system (tables exist but empty)
3. Deploy Ethereum bridge contracts
4. Test transaction creation/broadcasting

## DATABASE CONNECTION

Port: 30000 (SQL), 30001 (Web UI)
Certs: /home/ash/qubitcoin/data/certs/

Connection string:
```
postgresql://root@localhost:30000/qbc?sslmode=verify-full&sslrootcert=/home/ash/qubitcoin/data/certs/ca.crt&sslcert=/home/ash/qubitcoin/data/certs/client.root.crt&sslkey=/home/ash/qubitcoin/data/certs/client.root.key
```

## VERIFICATION COMMANDS
```bash
# Check database (PORT 30000!)
cockroach sql --certs-dir=/home/ash/qubitcoin/data/certs \
  --host=localhost:30000 --database=qbc \
  -e "SELECT COUNT(*) as blocks FROM blocks;"

# Check node
curl -s http://localhost:5000/health | python3 -m json.tool
```

## PROJECT FILES

All source code available in /mnt/project/
- src-*.txt files contain all Python code
- qubitcoin-scripts.txt has database migrations
- Directory structure in more_scripts___directory_strucructure.txt

## RUNNING SYSTEM

Terminal 1:
```bash
cockroach start-single-node \
  --certs-dir=/home/ash/qubitcoin/data/certs \
  --listen-addr=localhost:30000 \
  --http-addr=localhost:30001 \
  --store=/home/ash/qubitcoin/data/cockroach
```

Terminal 2:
```bash
cd ~/qubitcoin
source venv/bin/activate
python3 -m qubitcoin.node
```

Working directory: /home/ash/qubitcoin/
