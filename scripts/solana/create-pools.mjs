import {
  Raydium,
  TxVersion,
  CREATE_CPMM_POOL_PROGRAM,
  CREATE_CPMM_POOL_FEE_ACC,
} from '@raydium-io/raydium-sdk-v2'
import { Connection, Keypair, sendAndConfirmRawTransaction } from '@solana/web3.js'
import { TOKEN_PROGRAM_ID } from '@solana/spl-token'
import BN from 'bn.js'
import bs58 from 'bs58'
import fs from 'fs'

// Load private key from secure_key.env
const envContent = fs.readFileSync('/root/Qubitcoin/secure_key.env', 'utf8')
const privateKeyMatch = envContent.match(/SOLANA_PRIVATE_KEY=(.+)/)
if (!privateKeyMatch) throw new Error('SOLANA_PRIVATE_KEY not found in secure_key.env')
const owner = Keypair.fromSecretKey(bs58.decode(privateKeyMatch[1].trim()))

const connection = new Connection('https://solana-mainnet.g.alchemy.com/v2/TFeCF4UjX3XW73qYcc0pWfFP9aVcmuNK', {
  commitment: 'confirmed',
  wsEndpoint: undefined, // Disable websocket - Alchemy doesn't support signatureSubscribe
})

const WQBC_MINT = 'Ew7o13E7gwcbYsv4aRpoZEKonTW6snAGYHerD9j3C1Kf'
const WQUSD_MINT = 'CfipKUW1vTGt1Y9jcFwDsrafD3bvxaD9PUMD9zjRRWR3'
const SOL_MINT = 'So11111111111111111111111111111111111111112'

const DECIMALS = 8
const MULTIPLIER = 10 ** DECIMALS
const SOL_DECIMALS = 9
const SOL_MULTIPLIER = 10 ** SOL_DECIMALS

async function pollForConfirmation(connection, signature, timeout = 90000) {
  const start = Date.now()
  console.log(`Polling for confirmation of ${signature}...`)
  while (Date.now() - start < timeout) {
    const status = await connection.getSignatureStatus(signature)
    if (status?.value?.confirmationStatus === 'confirmed' || status?.value?.confirmationStatus === 'finalized') {
      if (status.value.err) {
        throw new Error(`Transaction failed: ${JSON.stringify(status.value.err)}`)
      }
      console.log(`Confirmed! Status: ${status.value.confirmationStatus}`)
      return status
    }
    await new Promise(r => setTimeout(r, 2000))
  }
  throw new Error('Transaction confirmation timeout')
}

async function createCpmmPool(raydium, mintAddress, tokenAmount, solAmount, tokenName) {
  console.log(`\n=== Creating ${tokenName}/SOL CPMM Pool ===`)
  console.log(`Token: ${mintAddress}`)
  console.log(`Token amount: ${tokenAmount / MULTIPLIER} ${tokenName}`)
  console.log(`SOL amount: ${solAmount / SOL_MULTIPLIER} SOL`)

  const mintA = {
    address: mintAddress,
    programId: TOKEN_PROGRAM_ID.toBase58(),
    decimals: DECIMALS,
  }
  const mintB = {
    address: SOL_MINT,
    programId: TOKEN_PROGRAM_ID.toBase58(),
    decimals: SOL_DECIMALS,
  }

  const feeConfigs = await raydium.api.getCpmmConfigs()
  console.log(`Available fee tiers: ${feeConfigs.map(c => c.tradeFeeRate / 10000 + '%').join(', ')}`)

  // Use 0.25% fee tier
  const feeConfig = feeConfigs.find(c => c.tradeFeeRate === 2500) || feeConfigs[0]
  console.log(`Using fee: ${feeConfig.tradeFeeRate / 10000}% (config: ${feeConfig.id})`)

  const { execute, extInfo, transaction } = await raydium.cpmm.createPool({
    programId: CREATE_CPMM_POOL_PROGRAM,
    poolFeeAccount: CREATE_CPMM_POOL_FEE_ACC,
    mintA,
    mintB,
    mintAAmount: new BN(tokenAmount.toString()),
    mintBAmount: new BN(solAmount.toString()),
    startTime: new BN(0),
    feeConfig,
    associatedOnly: false,
    ownerInfo: { useSOLBalance: true },
    txVersion: TxVersion.V0,
    computeBudgetConfig: {
      units: 600000,
      microLamports: 100000,
    },
  })

  const poolId = extInfo.address.poolId.toString()
  console.log(`Pool ID: ${poolId}`)

  // Send raw transaction manually instead of using SDK's sendAndConfirm (which uses websocket)
  console.log(`Sending transaction...`)
  const serialized = transaction.serialize()
  const txSignature = await connection.sendRawTransaction(serialized, {
    skipPreflight: false,
    preflightCommitment: 'confirmed',
  })
  console.log(`Sent! Signature: ${txSignature}`)

  await pollForConfirmation(connection, txSignature)

  const poolKeys = Object.keys(extInfo.address).reduce(
    (acc, cur) => ({ ...acc, [cur]: extInfo.address[cur].toString() }),
    {}
  )
  console.log(`Pool keys:`, poolKeys)

  return { txId: txSignature, poolId, poolKeys }
}

async function main() {
  console.log(`Wallet: ${owner.publicKey.toBase58()}`)
  console.log(`Connecting to Solana mainnet...`)

  const raydium = await Raydium.load({
    owner,
    connection,
    cluster: 'mainnet',
    disableFeatureCheck: true,
    disableLoadToken: false,
    blockhashCommitment: 'finalized',
  })

  const balance = await connection.getBalance(owner.publicKey)
  console.log(`SOL Balance: ${balance / SOL_MULTIPLIER} SOL`)

  if (balance < 0.15 * SOL_MULTIPLIER) {
    console.error('Need at least 0.15 SOL')
    process.exit(1)
  }

  const poolChoice = process.argv[2] || 'both'

  // SOL price ~$89 (March 21, 2026)
  // wQBC target = $0.25 → 1 SOL = 356 wQBC
  // wQUSD target = $1.00 → 1 SOL = 89 wQUSD

  if (poolChoice === 'wqbc' || poolChoice === 'both') {
    // Need ~0.15 SOL rent + liquidity SOL
    // Use minimal: 3.56 wQBC paired with 0.01 SOL → price = $0.25/wQBC (356 wQBC/SOL)
    const wqbcAmount = Math.floor(3.56 * MULTIPLIER)  // 3.56 wQBC
    const solForQbc = Math.floor(0.01 * SOL_MULTIPLIER) // 0.01 SOL
    console.log(`\nTarget price: $0.25/wQBC (ratio: ${3.56 / 0.01} wQBC/SOL)`)

    try {
      const result = await createCpmmPool(raydium, WQBC_MINT, wqbcAmount, solForQbc, 'wQBC')
      console.log(`\n✓ wQBC/SOL Pool created!`)
      console.log(`  Pool ID: ${result.poolId}`)
      console.log(`  Tx: ${result.txId}`)
    } catch (e) {
      console.error('Failed to create wQBC/SOL pool:', e.message || e)
      if (e.logs) console.error('Logs:', e.logs)
    }
  }

  if (poolChoice === 'wqusd' || poolChoice === 'both') {
    // 0.89 wQUSD paired with 0.01 SOL → price = $1.00/wQUSD (89 wQUSD/SOL)
    const wqusdAmount = Math.floor(0.89 * MULTIPLIER)  // 0.89 wQUSD
    const solForQusd = Math.floor(0.01 * SOL_MULTIPLIER)  // 0.01 SOL
    console.log(`\nTarget price: $1.00/wQUSD (ratio: ${0.89 / 0.01} wQUSD/SOL)`)

    try {
      const result = await createCpmmPool(raydium, WQUSD_MINT, wqusdAmount, solForQusd, 'wQUSD')
      console.log(`\n✓ wQUSD/SOL Pool created!`)
      console.log(`  Pool ID: ${result.poolId}`)
      console.log(`  Tx: ${result.txId}`)
    } catch (e) {
      console.error('Failed to create wQUSD/SOL pool:', e.message || e)
      if (e.logs) console.error('Logs:', e.logs)
    }
  }

  console.log('\nDone!')
  process.exit(0)
}

main().catch(e => { console.error(e); process.exit(1) })
