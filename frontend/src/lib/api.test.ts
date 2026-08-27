import { describe, expect, it, vi } from "vitest";
import { filenameFromContentDisposition, normalizeGraphData } from "./api";

describe("filenameFromContentDisposition", () => {
  it("uses the server filename, including RFC 5987 encoded names", () => {
    expect(filenameFromContentDisposition('attachment; filename="statement_4_report.pdf"', "fallback.pdf")).toBe(
      "statement_4_report.pdf",
    );
    expect(filenameFromContentDisposition("attachment; filename*=UTF-8''evidence%20bundle.json", "fallback.pdf")).toBe(
      "evidence bundle.json",
    );
  });

  it("falls back when the header is absent or malformed", () => {
    expect(filenameFromContentDisposition(null, "fallback.pdf")).toBe("fallback.pdf");
    expect(filenameFromContentDisposition("attachment; filename*=UTF-8''%E0%A4", "fallback.pdf")).toBe("fallback.pdf");
  });
});

describe("normalizeGraphData", () => {
  it("drops malformed graph members while preserving valid nodes and edges", () => {
    expect(
      normalizeGraphData({
        nodes: [
          { id: "ACCT_1", label: "Subject", flow: 42 },
          { id: 2, label: "Invalid" },
        ],
        edges: [
          { source: "ACCT_1", target: "MISSING", row_id: "bad" },
          { source: "ACCT_1", target: "ACCT_1", row_id: "row-1", amount: "12", channel: null },
        ],
        cycles: [{ cycle_id: "cycle-1", nodes: ["ACCT_1", 4], hop_count: "2", cycle_risk_score: 0.9 }],
        mule_row_ids: ["row-1", null],
      }),
    ).toEqual({
      nodes: [{ id: "ACCT_1", label: "Subject", flow: 42 }],
      edges: [{ source: "ACCT_1", target: "ACCT_1", row_id: "row-1", amount: 12, channel: "" }],
      cycles: [{ cycle_id: "cycle-1", nodes: ["ACCT_1"], hop_count: 2, cycle_risk_score: 0.9 }],
      mule_row_ids: ["row-1"],
      mule_nodes: [],
    });
  });
});

describe("SAR draft API adapter", () => {
  it("keeps draft exports evidence-specific and URL-encodes finding IDs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("draft", {
      headers: { "Content-Disposition": 'attachment; filename="case_2_finding_a_b_sar_str_draft.html"' },
    }));
    vi.stubGlobal("fetch", fetchMock);
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(window.URL, "createObjectURL", { value: createObjectURL, configurable: true });
    Object.defineProperty(window.URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    const { api } = await import("./api");
    await api.exportSarDraft(2, "a/b", "html");

    expect(fetchMock).toHaveBeenCalledWith("/api/cases/2/findings/a%2Fb/sar-draft/export?format=html");
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });
});
