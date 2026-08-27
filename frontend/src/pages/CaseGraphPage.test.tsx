import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CaseGraphPage } from "./CaseGraphPage";
import { api } from "../lib/api";

vi.mock("../components/CaseGraphCanvas", () => ({
  CaseGraphCanvas: ({ onNodeClick }: { onNodeClick: (id: string) => void }) => <button onClick={() => onNodeClick("node-a")}>Select Rohan Kumar</button>,
}));

const graph = {
  case_id: 7,
  nodes: [
    { id: "node-a", kind: "subject_account", label: "Rohan Kumar", institution: "Demo Bank", risk_tier: "high", evidence: {} },
    { id: "node-b", kind: "counterparty_observation", label: "Shell Co", institution: null, risk_tier: "normal", evidence: {} },
  ],
  edges: [{ id: "edge-a", source: "node-a", target: "node-b", amount: 475000, txn_date: "2026-08-18", source_statement_ids: [1], source_row_ids: ["row-1"], resolution_method: "mirror", is_finding_edge: true }],
  findings: [{ id: "finding-a", kind: "conserved_flow_cycle", risk_score: 0.92, hop_count: 3, node_sequence: ["node-a", "node-b"], edge_ids: ["edge-a"], source_row_ids: ["row-1"] }],
  limitations: ["Names are never automatically merged across statements."],
};

function renderPage() {
  const router = createMemoryRouter([{ path: "/cases/:caseId/graph", element: <CaseGraphPage /> }], { initialEntries: ["/cases/7/graph"] });
  return render(<RouterProvider router={router} />);
}

describe("CaseGraphPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listCases").mockResolvedValue([{ id: 7, name: "Project Trident", description: "Three-statement ring", created_ts: "2026-08-18", analyzed_ts: "2026-08-20", analysis_version: 1, statement_ids: [1, 2, 3] }]);
    vi.spyOn(api, "getCase").mockResolvedValue({ id: 7, name: "Project Trident", description: "Three-statement ring", created_ts: "2026-08-18", analyzed_ts: "2026-08-20", analysis_version: 1, statement_ids: [1, 2, 3] });
    vi.spyOn(api, "getCaseGraph").mockResolvedValue(graph);
    vi.spyOn(api, "getCaseFinding").mockResolvedValue({ id: "finding-a", kind: "conserved_flow_cycle", risk_score: 0.92, hop_count: 3, node_sequence: ["node-a", "node-b"], edge_ids: ["edge-a"], source_row_ids: ["row-1"], case_id: 7, source_statement_ids: [1], detail: { formula: "Conserved flow", limitations: ["Date precision"] }, ordered_hops: [{ edge_id: "edge-a", source: "node-a", target: "node-b", amount: 475000, txn_date: "2026-08-18", source_row_ids: ["row-1"], source_statement_ids: [1] }] });
    vi.spyOn(api, "getCaseNodeTransactions").mockResolvedValue({ total: 1, offset: 0, limit: 10, items: [{ edge_id: "edge-a", direction: "out", row_id: "row-1", statement_id: 1, source_filename: "rohan.csv", txn_date: "2026-08-18", amount: 475000, narration: "transfer to Shell Co", reference_no: "TRI-1", debit_amount: 475000, credit_amount: null }] });
  });

  it("loads a case finding and opens a source-backed node drawer", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Project Trident" })).toBeInTheDocument();
    expect(screen.getByText("3-hop conserved flow")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Select Rohan Kumar" }));
    expect(await screen.findByRole("dialog", { name: "Node transaction evidence" })).toBeInTheDocument();
    expect(screen.getByText("transfer to Shell Co")).toBeInTheDocument();
    await waitFor(() => expect(api.getCaseNodeTransactions).toHaveBeenCalledWith(7, "node-a", 0, 10, "finding-a"));
  });
});
