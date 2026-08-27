import { ChevronLeft, ChevronRight } from "lucide-react";
import { TransactionRow } from "../lib/api";
import { Badge, TBody, THead, Table, Td, Th, formatDate, inr } from "./ui";

type TransactionTableProps = {
  rows: TransactionRow[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

function amount(value: number | null): string {
  if (value == null || Number.isNaN(Number(value))) return "";
  return inr.format(Number(value));
}

export function TransactionTable({ rows, total, page, pageSize, onPageChange }: TransactionTableProps) {
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div>
      <Table minWidth={880}>
        <THead>
          <Th>Date</Th>
          <Th>Narration</Th>
          <Th align="right">Debit</Th>
          <Th align="right">Credit</Th>
          <Th align="right">Balance</Th>
          <Th>Channel</Th>
          <Th>Category</Th>
          <Th>Flags</Th>
        </THead>
        <TBody>
          {rows.map((r) => {
            const flagged = r.tagged_rules.length > 0 || r.tagged_cycles.length > 0;
            return (
              <tr
                key={r.row_id}
                className={`transition-colors ${flagged ? "bg-red-50/40" : "hover:bg-ink-50/70"}`}
              >
                <Td className="whitespace-nowrap text-[12px] text-ink-500">{formatDate(r.txn_date)}</Td>
                <Td className="max-w-[280px] truncate text-[12px] text-ink-700" >
                  <span title={r.narration}>{r.narration}</span>
                </Td>
                <Td align="right" className="num text-[12px] font-medium text-red-600">
                  {amount(r.debit_amount)}
                </Td>
                <Td align="right" className="num text-[12px] font-medium text-emerald-700">
                  {amount(r.credit_amount)}
                </Td>
                <Td align="right" className="num text-[12px] text-ink-500">
                  {amount(r.balance_after)}
                </Td>
                <Td className="text-[11px] uppercase tracking-wide text-ink-400">{r.channel ?? "—"}</Td>
                <Td className="text-[12px] text-ink-500">{r.category ?? "—"}</Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    {r.tagged_rules.length > 0 && (
                      <Badge tone="danger">{r.tagged_rules.length} rule</Badge>
                    )}
                    {r.tagged_cycles.length > 0 && (
                      <Badge tone="accent">{r.tagged_cycles.length} cycle</Badge>
                    )}
                    {!flagged && <span className="text-[11px] text-ink-300">—</span>}
                  </div>
                </Td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <Td className="py-6 text-center text-[12px] text-ink-400" align="center">
                No transactions to display.
              </Td>
            </tr>
          )}
        </TBody>
      </Table>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-ink-100 bg-ink-50/50 px-4 py-2.5">
        <span className="num text-[11px] text-ink-400">
          Showing {from}–{to} of {total} rows
        </span>
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="inline-flex h-7 items-center gap-1 rounded-md border border-ink-200 bg-white px-2 text-[11px] font-medium text-ink-600 transition-colors hover:bg-ink-50 disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" /> Prev
            </button>
            <span className="num px-2 text-[11px] text-ink-500">
              Page {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="inline-flex h-7 items-center gap-1 rounded-md border border-ink-200 bg-white px-2 text-[11px] font-medium text-ink-600 transition-colors hover:bg-ink-50 disabled:opacity-40"
            >
              Next <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
