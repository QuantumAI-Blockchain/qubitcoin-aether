/**
 * IndexedDB offline cache for Qubitcoin frontend.
 *
 * Provides a TTL-based key-value cache backed by IndexedDB.
 * Used to cache chain info, block data, balance queries, and other
 * API responses for offline-first capability.
 */

const DB_NAME = "qbc-offline-cache";
const DB_VERSION = 1;
const STORE_NAME = "cache";

/** Default TTL values in milliseconds for different data categories. */
export const CacheTTL = {
  /** Chain info: 30 seconds (changes every block ~3.3s, but stale is okay) */
  CHAIN_INFO: 30_000,
  /** Block data: 24 hours (blocks are immutable once mined) */
  BLOCK_DATA: 86_400_000,
  /** Balance queries: 60 seconds (can change with each block) */
  BALANCE: 60_000,
  /** Phi / integration data: 30 seconds */
  PHI_DATA: 30_000,
  /** Knowledge graph stats: 60 seconds */
  KNOWLEDGE: 60_000,
  /** Mining stats: 15 seconds */
  MINING: 15_000,
  /** Economics / emission: 1 hour (rarely changes) */
  ECONOMICS: 3_600_000,
  /** QVM info: 5 minutes */
  QVM_INFO: 300_000,
  /** Default: 60 seconds */
  DEFAULT: 60_000,
} as const;

interface CacheEntry<T = unknown> {
  key: string;
  value: T;
  expiresAt: number;
  createdAt: number;
}

/** Open (or create) the IndexedDB database. */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is not available"));
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "key" });
        store.createIndex("expiresAt", "expiresAt", { unique: false });
      }
    };
  });
}

/** Execute a transaction on the cache store. */
async function withStore<T>(
  mode: IDBTransactionMode,
  callback: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode);
    const store = tx.objectStore(STORE_NAME);
    const request = callback(store);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

/**
 * Get a value from the cache.
 * Returns `null` if the key doesn't exist or the entry has expired.
 */
export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const entry = await withStore<CacheEntry<T> | undefined>(
      "readonly",
      (store) => store.get(key),
    );

    if (!entry) return null;

    // Check if expired
    if (Date.now() > entry.expiresAt) {
      // Don't block on deletion
      cacheDelete(key).catch(() => {});
      return null;
    }

    return entry.value;
  } catch {
    // IndexedDB not available (SSR, private browsing, etc.)
    return null;
  }
}

/**
 * Store a value in the cache with a TTL.
 */
export async function cacheSet<T>(
  key: string,
  value: T,
  ttlMs: number = CacheTTL.DEFAULT,
): Promise<void> {
  try {
    const entry: CacheEntry<T> = {
      key,
      value,
      createdAt: Date.now(),
      expiresAt: Date.now() + ttlMs,
    };
    await withStore("readwrite", (store) => store.put(entry));
  } catch {
    // Silently fail — cache is best-effort
  }
}

/**
 * Delete a specific key from the cache.
 */
export async function cacheDelete(key: string): Promise<void> {
  try {
    await withStore("readwrite", (store) => store.delete(key));
  } catch {
    // Silently fail
  }
}

/**
 * Clear all entries from the cache.
 */
export async function cacheClear(): Promise<void> {
  try {
    await withStore("readwrite", (store) => store.clear());
  } catch {
    // Silently fail
  }
}

/**
 * Remove all expired entries from the cache.
 * Call this periodically (e.g., on app load) to keep the store clean.
 */
export async function cacheEvictExpired(): Promise<number> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const index = store.index("expiresAt");
      const now = Date.now();
      const range = IDBKeyRange.upperBound(now);
      const request = index.openCursor(range);
      let deletedCount = 0;

      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          cursor.delete();
          deletedCount++;
          cursor.continue();
        }
      };

      tx.oncomplete = () => {
        db.close();
        resolve(deletedCount);
      };
      tx.onerror = () => {
        db.close();
        reject(tx.error);
      };
    });
  } catch {
    return 0;
  }
}

/**
 * Get-or-fetch pattern: returns cached data if fresh, otherwise fetches
 * from the provided async function and stores the result.
 */
export async function cacheGetOrFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlMs: number = CacheTTL.DEFAULT,
): Promise<T> {
  // Try cache first
  const cached = await cacheGet<T>(key);
  if (cached !== null) return cached;

  // Fetch fresh data
  const data = await fetcher();

  // Store in cache (don't await — fire and forget)
  cacheSet(key, data, ttlMs).catch(() => {});

  return data;
}

/**
 * Returns the approximate number of entries in the cache.
 */
export async function cacheSize(): Promise<number> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const store = tx.objectStore(STORE_NAME);
      const request = store.count();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      tx.oncomplete = () => db.close();
    });
  } catch {
    return 0;
  }
}
