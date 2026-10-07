import Link from "next/link";
import { formatDateTime } from "@/lib/format";
import type { DbCell, DbRows } from "@/lib/types";

const TIME_COLS = new Set(["ts", "created_at", "started_at", "ended_at", "updated_at", "built_at", "call_at"]);

function Cell({ column, value }: { column: string; value: DbCell }) {
  if (value === null || value === "") return <span className="text-dim">—</span>;
  if (typeof value === "object") {
    return (
      <span className="font-mono text-[12px] text-brand" title="float32 вектор (RAG хайлтад)">
        вектор {value.dims} · [{value.preview.join(", ")}, …]
      </span>
    );
  }
  if (typeof value === "number" && TIME_COLS.has(column) && value > 1e9) {
    return <span className="font-mono">{formatDateTime(value)}</span>;
  }
  const text = String(value);
  return <span title={text.length > 120 ? text : undefined}>{text.length > 120 ? `${text.slice(0, 120)}…` : text}</span>;
}

/** Нэг хүснэгтийн мөрүүд: хайлт, хуудаслалт (шинэ нь эхэндээ) */
export function DbTableView({ data, q }: { data: DbRows; q: string }) {
  const href = (offset: number) => `/database?${new URLSearchParams({ table: data.table, ...(q ? { q } : {}), offset: String(offset) })}`;
  const from = data.total ? data.offset + 1 : 0;
  const to = Math.min(data.offset + data.page, data.total);
  return (
    <div>
      <form className="mb-3 flex flex-wrap items-center gap-2" action="/database">
        <input type="hidden" name="table" value={data.table} />
        <input
          name="q"
          defaultValue={q}
          placeholder="Хайх (текст баганаас)…"
          aria-label="Хайх"
          className="min-w-[220px] flex-1 rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none"
        />
        <button className="cursor-pointer rounded-[10px] border-[1.5px] border-line-2 px-4 py-2 text-sm font-semibold hover:border-brand">Хайх</button>
        <span className="ml-auto font-mono text-[13px] text-muted">{from}–{to} / {data.total}</span>
      </form>
      <div className="overflow-x-auto rounded-[12px] border border-line">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-panel-2">
            <tr>{data.columns.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2 font-mono text-[11px] uppercase tracking-wider text-muted">{c}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.map((row, i) => (
              <tr key={i} className="border-t border-line align-top">
                {row.map((v, j) => <td key={j} className="max-w-[420px] px-3 py-2"><Cell column={data.columns[j]} value={v} /></td>)}
              </tr>
            ))}
            {!data.rows.length && (
              <tr><td colSpan={data.columns.length} className="px-3 py-6 text-center text-muted">Мөр алга</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex justify-between text-sm">
        {data.offset > 0 ? <Link href={href(Math.max(0, data.offset - data.page))} className="hover:underline">← Өмнөх</Link> : <span />}
        {to < data.total ? <Link href={href(data.offset + data.page)} className="hover:underline">Дараах →</Link> : <span />}
      </div>
    </div>
  );
}
