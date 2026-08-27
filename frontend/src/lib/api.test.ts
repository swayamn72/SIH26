import { describe, expect, it } from "vitest";
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
