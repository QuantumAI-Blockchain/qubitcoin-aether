import { describe, it, expect } from "vitest";

describe("API module", () => {
  it("exports typed helper functions", async () => {
    const { api } = await import("@/lib/api");
    expect(api).toBeDefined();
    expect(typeof api.getChainInfo).toBe("function");
    expect(typeof api.getHealth).toBe("function");
    expect(typeof api.getBalance).toBe("function");
    expect(typeof api.getMiningStats).toBe("function");
    expect(typeof api.getPhi).toBe("function");
    expect(typeof api.getPhiHistory).toBe("function");
    expect(typeof api.getKnowledge).toBe("function");
    expect(typeof api.getContract).toBe("function");
    expect(typeof api.getContractStorage).toBe("function");
    expect(typeof api.getUTXOs).toBe("function");
    expect(typeof api.getMempool).toBe("function");
    expect(typeof api.createChatSession).toBe("function");
    expect(typeof api.sendChatMessage).toBe("function");
  });

  it("exports typed interfaces", async () => {
    // Verify we can import the types without error
    const mod = await import("@/lib/api");
    expect(mod.get).toBeDefined();
    expect(mod.post).toBeDefined();
  });
});
