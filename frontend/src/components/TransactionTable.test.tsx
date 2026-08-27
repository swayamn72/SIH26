import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TransactionTable } from "./TransactionTable";

describe("TransactionTable", () => {
  it("renders rows with absent optional tags as unflagged", () => {
    render(
      <TransactionTable
        rows={[
          {
            row_id: "row-1",
            txn_date: "2026-08-27",
            value_date: null,
            narration: "Salary credit",
            reference_no: null,
            debit_amount: null,
            credit_amount: 1000,
            balance_after: 1000,
            channel: null,
            category: null,
            counterparty_id: null,
            row_confidence: 1,
            is_reconciled: true,
            tagged_rules: [],
            tagged_cycles: [],
          },
        ]}
        total={1}
        page={1}
        pageSize={100}
        onPageChange={() => undefined}
      />,
    );

    expect(screen.getByText("Salary credit")).toBeInTheDocument();
    expect(screen.getByText("Showing 1–1 of 1 rows")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(3);
  });
});
