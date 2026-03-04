/**
 * Offline Transaction Queue
 *
 * Stores signed transactions in IndexedDB when offline,
 * and broadcasts them when connectivity is restored.
 */

const DB_NAME = "qbc-offline-tx";
const STORE_NAME = "pending-transactions";
const DB_VERSION = 1;

export interface OfflineTransaction {
  id: string;
  to: string;
  amount: string;
  signedPayload: string;
  createdAt: number;
  status: "pending" | "broadcasting" | "confirmed" | "failed";
  error?: string;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function queueTransaction(tx: Omit<OfflineTransaction, "id" | "createdAt" | "status">): Promise<string> {
  const id = crypto.randomUUID();
  const record: OfflineTransaction = {
    ...tx,
    id,
    createdAt: Date.now(),
    status: "pending",
  };
  const db = await openDB();
  const txn = db.transaction(STORE_NAME, "readwrite");
  txn.objectStore(STORE_NAME).add(record);
  await new Promise<void>((resolve, reject) => {
    txn.oncomplete = () => resolve();
    txn.onerror = () => reject(txn.error);
  });
  return id;
}

export async function getPendingTransactions(): Promise<OfflineTransaction[]> {
  const db = await openDB();
  const txn = db.transaction(STORE_NAME, "readonly");
  const store = txn.objectStore(STORE_NAME);
  return new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function updateTransactionStatus(
  id: string,
  status: OfflineTransaction["status"],
  error?: string,
): Promise<void> {
  const db = await openDB();
  const txn = db.transaction(STORE_NAME, "readwrite");
  const store = txn.objectStore(STORE_NAME);
  const existing: OfflineTransaction | undefined = await new Promise((resolve) => {
    const req = store.get(id);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve(undefined);
  });
  if (existing) {
    existing.status = status;
    if (error) existing.error = error;
    store.put(existing);
  }
  await new Promise<void>((resolve) => {
    txn.oncomplete = () => resolve();
    txn.onerror = () => resolve();
  });
}

export async function removeTransaction(id: string): Promise<void> {
  const db = await openDB();
  const txn = db.transaction(STORE_NAME, "readwrite");
  txn.objectStore(STORE_NAME).delete(id);
  await new Promise<void>((resolve) => {
    txn.oncomplete = () => resolve();
    txn.onerror = () => resolve();
  });
}

export async function broadcastPendingTransactions(
  rpcUrl: string,
): Promise<{ sent: number; failed: number }> {
  const pending = await getPendingTransactions();
  const toSend = pending.filter((tx) => tx.status === "pending");
  let sent = 0;
  let failed = 0;

  for (const tx of toSend) {
    try {
      await updateTransactionStatus(tx.id, "broadcasting");
      const resp = await fetch(`${rpcUrl}/transaction/broadcast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signed_tx: tx.signedPayload }),
      });
      if (resp.ok) {
        await updateTransactionStatus(tx.id, "confirmed");
        sent++;
      } else {
        await updateTransactionStatus(tx.id, "failed", `HTTP ${resp.status}`);
        failed++;
      }
    } catch (err) {
      await updateTransactionStatus(tx.id, "pending");
      failed++;
    }
  }

  return { sent, failed };
}

/** Listen for online events and auto-broadcast. */
export function setupAutoSync(rpcUrl: string): () => void {
  const handler = () => {
    broadcastPendingTransactions(rpcUrl);
  };
  window.addEventListener("online", handler);
  return () => window.removeEventListener("online", handler);
}

export function getQueueCount(): Promise<number> {
  return getPendingTransactions().then((txs) =>
    txs.filter((t) => t.status === "pending").length,
  );
}
