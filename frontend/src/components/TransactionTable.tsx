type TransactionRow = {
  row_id: string;
  txn_date: string;
  narration: string;
  debit_amount: number | null;
  credit_amount: number | null;
  balance_after: number | null;
  channel: string | null;
  category: string | null;
  row_confidence: number;
  tagged_rules: string[];
  tagged_cycles: string[];
};

type TransactionTableProps = {
  rows: TransactionRow[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

export function TransactionTable({ rows, total, page, pageSize, onPageChange }: TransactionTableProps) {
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm min-w-[650px]">
        <thead>
          <tr className="border-b bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Narration</th>
            <th className="px-3 py-2 text-right">Debit</th>
            <th className="px-3 py-2 text-right">Credit</th>
            <th className="px-3 py-2 text-right">Balance</th>
            <th className="px-3 py-2">Channel</th>
            <th className="px-3 py-2">Category</th>
            <th className="px-3 py-2">Flags</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r) => (
            <tr key={r.row_id} className="hover:bg-gray-50">
              <td className="px-3 py-2 whitespace-nowrap">{r.txn_date}</td>
              <td className="px-3 py-2 max-w-xs truncate" title={r.narration}>{r.narration}</td>
              <td className="px-3 py-2 text-right text-red-600">{r.debit_amount != null && !isNaN(Number(r.debit_amount)) ? Number(r.debit_amount).toFixed(2) : ""}</td>
              <td className="px-3 py-2 text-right text-green-600">{r.credit_amount != null && !isNaN(Number(r.credit_amount)) ? Number(r.credit_amount).toFixed(2) : ""}</td>
              <td className="px-3 py-2 text-right">{r.balance_after != null && !isNaN(Number(r.balance_after)) ? Number(r.balance_after).toFixed(2) : ""}</td>
              <td className="px-3 py-2">{r.channel ?? ""}</td>
              <td className="px-3 py-2">{r.category ?? ""}</td>
              <td className="px-3 py-2">
                {r.tagged_rules.length > 0 && (
                  <span className="inline-block bg-red-100 text-red-700 text-xs px-1.5 py-0.5 rounded mr-1">
                    R{r.tagged_rules.length}
                  </span>
                )}
                {r.tagged_cycles.length > 0 && (
                  <span className="inline-block bg-purple-100 text-purple-700 text-xs px-1.5 py-0.5 rounded">
                    C{r.tagged_cycles.length}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 border-t text-sm text-gray-500">
          <span>{total} rows</span>
          <div className="flex gap-1">
            <button
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-30"
            >
              Prev
            </button>
            <span className="px-2 py-1">{page} / {totalPages}</span>
            <button
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
