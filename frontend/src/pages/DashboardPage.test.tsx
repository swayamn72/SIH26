import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "./DashboardPage";
import { api } from "../lib/api";

vi.mock("../lib/StatementContext", () => ({
  useStatement: () => ({
    currentId: 1,
    setCurrentId: vi.fn(),
    statements: [],
    currentStatement: null,
  }),
}));

vi.mock("../components/WhyFlaggedPanel", () => ({ WhyFlaggedPanel: () => null }));
vi.mock("../components/RuleTriggerList", () => ({ RuleTriggerList: () => null }));
vi.mock("../components/NarrativePanel", () => ({ NarrativePanel: () => null }));

const evidence = {
  account_summary: {},
  final_decision: {},
  triggered_rules: [],
  features: [],
  cycles_detected: [],
  anomaly_detail: null,
  supervised_detail: null,
  guardrail_log: {},
};

function renderDashboard(path = "/dashboard/1") {
  const router = createMemoryRouter([{ path: "/dashboard/:id", element: <DashboardPage /> }], {
    initialEntries: [path],
  });
  return { router, ...render(<RouterProvider router={router} />) };
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getEvidence").mockResolvedValue(evidence);
    vi.spyOn(api, "getWhyFlagged").mockRejectedValue(new Error("not needed"));
    vi.spyOn(api, "getNarrative").mockRejectedValue(new Error("not needed"));
  });

  it("refetches transactions when the audit-table page changes", async () => {
    const getTransactions = vi.spyOn(api, "getTransactions").mockImplementation(async (_id, page = 1) => ({
      rows: [
        {
          row_id: `row-${page}`,
          txn_date: "2026-08-27",
          value_date: null,
          narration: `Page ${page}`,
          reference_no: null,
          debit_amount: null,
          credit_amount: 10,
          balance_after: 10,
          channel: null,
          category: null,
          counterparty_id: null,
          row_confidence: 1,
          is_reconciled: true,
          tagged_rules: [],
          tagged_cycles: [],
        },
      ],
      total: 101,
      page,
      page_size: 100,
    }));

    renderDashboard();
    await screen.findByText("Page 1");
    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => expect(getTransactions).toHaveBeenLastCalledWith(1, 2));
    expect(await screen.findByText("Page 2")).toBeInTheDocument();
    expect(api.getEvidence).toHaveBeenCalledTimes(1);
    expect(api.getWhyFlagged).toHaveBeenCalledTimes(1);
    expect(api.getNarrative).toHaveBeenCalledTimes(1);
  });

  it("ignores stale transaction responses after changing cases", async () => {
    let resolveFirst: ((value: Awaited<ReturnType<typeof api.getTransactions>>) => void) | undefined;
    const first = new Promise<Awaited<ReturnType<typeof api.getTransactions>>>((resolve) => {
      resolveFirst = resolve;
    });
    vi.spyOn(api, "getTransactions").mockImplementation((id) => {
      if (id === 1) return first;
      return Promise.resolve({
        rows: [
          {
            row_id: "second",
            txn_date: "2026-08-27",
            value_date: null,
            narration: "Current case row",
            reference_no: null,
            debit_amount: null,
            credit_amount: 10,
            balance_after: 10,
            channel: null,
            category: null,
            counterparty_id: null,
            row_confidence: 1,
            is_reconciled: true,
            tagged_rules: [],
            tagged_cycles: [],
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
      });
    });

    const { router } = renderDashboard();
    await waitFor(() => expect(api.getTransactions).toHaveBeenCalledWith(1, 1));
    await router.navigate("/dashboard/2");

    expect(await screen.findByText("Current case row")).toBeInTheDocument();
    resolveFirst?.({
      rows: [
        {
          row_id: "stale",
          txn_date: "2026-08-27",
          value_date: null,
          narration: "Stale row",
          reference_no: null,
          debit_amount: null,
          credit_amount: 10,
          balance_after: 10,
          channel: null,
          category: null,
          counterparty_id: null,
          row_confidence: 1,
          is_reconciled: true,
          tagged_rules: [],
          tagged_cycles: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });
    await waitFor(() => expect(screen.queryByText("Stale row")).not.toBeInTheDocument());
  });
});
