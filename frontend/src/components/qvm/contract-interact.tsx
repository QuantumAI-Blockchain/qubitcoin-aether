"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import { Card } from "@/components/ui/card";

interface ABIInput {
  name: string;
  type: string;
}

interface ABIFunction {
  name: string;
  type: "function";
  stateMutability: string;
  inputs: ABIInput[];
  outputs: ABIInput[];
}

interface CallResult {
  success: boolean;
  result: string;
  gas_used: number;
}

function parseABI(raw: string): ABIFunction[] {
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item: { type?: string }) => item.type === "function",
    ) as ABIFunction[];
  } catch {
    return [];
  }
}

export function ContractInteract() {
  const [contractAddress, setContractAddress] = useState("");
  const [abiText, setAbiText] = useState("");
  const [functions, setFunctions] = useState<ABIFunction[]>([]);
  const [selectedFn, setSelectedFn] = useState<ABIFunction | null>(null);
  const [inputValues, setInputValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<CallResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleParseABI() {
    const fns = parseABI(abiText);
    setFunctions(fns);
    setSelectedFn(null);
    setResult(null);
    setError(fns.length === 0 && abiText.trim() ? "Invalid ABI or no functions found" : null);
  }

  function handleSelectFn(fn: ABIFunction) {
    setSelectedFn(fn);
    setInputValues({});
    setResult(null);
    setError(null);
  }

  async function handleCall() {
    if (!selectedFn || !contractAddress.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const args = selectedFn.inputs.map((inp) => inputValues[inp.name] ?? "");
      const res = await post<CallResult>("/qvm/call", {
        contract: contractAddress.trim(),
        function: selectedFn.name,
        args,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Call failed");
    } finally {
      setLoading(false);
    }
  }

  const isReadOnly =
    selectedFn?.stateMutability === "view" ||
    selectedFn?.stateMutability === "pure";

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
        Contract Interaction
      </h3>

      <div className="space-y-4">
        {/* Contract address */}
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Contract Address
          </label>
          <input
            value={contractAddress}
            onChange={(e) => setContractAddress(e.target.value)}
            placeholder="0x..."
            className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>

        {/* ABI input */}
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Contract ABI (JSON)
          </label>
          <textarea
            rows={4}
            value={abiText}
            onChange={(e) => setAbiText(e.target.value)}
            placeholder='[{"type":"function","name":"balanceOf","inputs":[{"name":"account","type":"address"}],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"}]'
            className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
          <button
            onClick={handleParseABI}
            disabled={!abiText.trim()}
            className="mt-2 rounded-lg bg-quantum-violet/20 px-4 py-2 text-xs font-medium text-quantum-violet transition hover:bg-quantum-violet/30 disabled:opacity-40"
          >
            Parse ABI
          </button>
        </div>

        {/* Function selector */}
        {functions.length > 0 && (
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Function ({functions.length} found)
            </label>
            <div className="flex flex-wrap gap-2">
              {functions.map((fn) => (
                <button
                  key={fn.name}
                  onClick={() => handleSelectFn(fn)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                    selectedFn?.name === fn.name
                      ? "bg-quantum-green text-void"
                      : "bg-surface-light text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {fn.name}
                  <span className="ml-1 opacity-60">
                    ({fn.stateMutability})
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Function inputs */}
        {selectedFn && (
          <div className="space-y-3 rounded-lg border border-surface-light bg-void/50 p-4">
            <p className="text-sm font-medium text-quantum-green">
              {selectedFn.name}
              <span className="ml-2 text-xs text-text-secondary">
                {isReadOnly ? "(read-only)" : "(write)"}
              </span>
            </p>

            {selectedFn.inputs.length === 0 && (
              <p className="text-xs text-text-secondary">No inputs required</p>
            )}

            {selectedFn.inputs.map((inp) => (
              <div key={inp.name}>
                <label className="mb-1 block text-xs text-text-secondary">
                  {inp.name}{" "}
                  <span className="text-quantum-violet">({inp.type})</span>
                </label>
                <input
                  value={inputValues[inp.name] ?? ""}
                  onChange={(e) =>
                    setInputValues((prev) => ({
                      ...prev,
                      [inp.name]: e.target.value,
                    }))
                  }
                  placeholder={inp.type}
                  className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
                />
              </div>
            ))}

            <button
              onClick={handleCall}
              disabled={loading || !contractAddress.trim()}
              className={`rounded-lg px-5 py-2.5 text-sm font-semibold transition disabled:opacity-40 ${
                isReadOnly
                  ? "bg-quantum-green/20 text-quantum-green hover:bg-quantum-green/30"
                  : "bg-quantum-violet px-6 text-white hover:bg-quantum-violet/80"
              }`}
            >
              {loading ? "Calling..." : isReadOnly ? "Call (Read)" : "Send Transaction"}
            </button>

            {/* Outputs */}
            {selectedFn.outputs.length > 0 && (
              <p className="text-xs text-text-secondary">
                Returns:{" "}
                {selectedFn.outputs
                  .map((o) => `${o.name || "result"} (${o.type})`)
                  .join(", ")}
              </p>
            )}
          </div>
        )}

        {/* Result */}
        {result && (
          <div
            className={`rounded-lg border p-4 ${
              result.success
                ? "border-quantum-green/30 bg-quantum-green/5"
                : "border-red-500/30 bg-red-500/5"
            }`}
          >
            <p className="text-xs font-medium text-text-secondary">
              {result.success ? "Success" : "Failed"} | Gas used:{" "}
              {result.gas_used.toLocaleString()}
            </p>
            <p className="mt-1 break-all font-[family-name:var(--font-mono)] text-sm text-text-primary">
              {result.result}
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}
      </div>
    </Card>
  );
}
