# INSTRUCTIONS FOR NEW CLAUDE INSTANCE

## STEP 1: Read Handover Document
```bash
view /home/ash/qubitcoin/HANDOVER.md
```

## STEP 2: Verify System Status
```bash
# Check database
cockroach sql --certs-dir=/home/ash/qubitcoin/data/certs \
  --host=localhost:30000 --database=qbc \
  -e "SHOW TABLES;"

# Check if node is running
ps aux | grep "python3 -m qubitcoin"

# Test RPC
curl http://localhost:5000/health
```

## STEP 3: Update Configuration
```bash
# Fix port in .env
sed -i 's|localhost:26257|localhost:30000|g' /home/ash/qubitcoin/.env

# Fix port in config.py
sed -i 's|localhost:26257|localhost:30000|g' /home/ash/qubitcoin/src/qubitcoin/config.py
```

## STEP 4: Review Project Files

All project files are in `/mnt/project/` - use view tool to read them.

Key files:
- `/mnt/project/src-*.txt` - All source code
- `/mnt/project/qubitcoin-scripts.txt` - Database scripts
- `/mnt/project/more_scripts___directory_strucructure.txt` - Project layout

## STEP 5: Priority Tasks

1. **Initialize Stablecoin System**
   - Populate oracle sources
   - Set collateral parameters
   - Initialize price feeds

2. **Deploy Bridge Contracts**
   - Compile Solidity contracts
   - Deploy to testnet
   - Set up relayer

3. **Test Transactions**
   - Create test transaction
   - Verify UTXO model
   - Test fee calculation

## WHAT USER NEEDS

User wants to:
1. Complete bridge setup (Ethereum ↔ Qubitcoin)
2. Initialize stablecoin system (QUSD)
3. Deploy smart contracts
4. Test full transaction flow

## CURRENT WORKING DIRECTORY
```
/home/ash/qubitcoin/
```

All commands should be run from here.
