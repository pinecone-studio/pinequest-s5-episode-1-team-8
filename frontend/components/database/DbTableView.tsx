"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { formatDateTime } from "@/lib/format";
import type { DbCell, DbRows } from "@/lib/types";

const TIME_COLS = new Set(["ts", "created_at", "started_at", "ended_at", "updated_at", "built_at", "call_at"]);

function Cell({ column, value }: { column: string; value: DbCell }) {
  const [copied, setCopied] = useState(false);

  const getCopyText = () => {
    if (value === null || value === "") return "";
    if (typeof value === "object") {
      return `vector dims:${value.dims} [${value.preview.join(", ")}]`;
    }
    if (typeof value === "number" && TIME_COLS.has(column) && value > 1e9) {
      return formatDateTime(value);
    }
    return String(value);
  };

  const handleCopy = async () => {
    const text = getCopyText();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <div className="group relative flex items-center justify-between gap-2">
      <div className="min-w-0 flex-1 truncate">
        {value === null || value === "" ? (
          <span className="text-dim">—</span>
        ) : typeof value === "object" ? (
          <span className="font-mono text-[12px] text-brand" title="float32 вектор (RAG хайлтад)">
            вектор {value.dims} · [{value.preview.join(", ")}, …]
          </span>
        ) : typeof value === "number" && TIME_COLS.has(column) && value > 1e9 ? (
          <span className="font-mono">{formatDateTime(value)}</span>
        ) : (
          (() => {
            const text = String(value);
            return <span title={text.length > 120 ? text : undefined}>{text.length > 120 ? `${text.slice(0, 120)}…` : text}</span>;
          })()
        )}
      </div>
      {value !== null && value !== "" && (
        <button
          type="button"
          onClick={handleCopy}
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 shrink-0 rounded bg-panel-2 px-1.5 py-0.5 text-[11px] font-medium text-muted hover:text-fg border border-line-2 transition cursor-pointer"
          title="Хуулах"
        >
          {copied ? "Хууллаа" : "Хуулах"}
        </button>
      )}
    </div>
  );
}

/** Нэг хүснэгтийн мөрүүд: хайлт, хуудаслалт (шинэ нь эхэндээ) */
export function DbTableView({ data, q }: { data: DbRows; q: string }) {
  const storageKey = `db-columns-${data.table}`;

  // Hydration mismatch-ээс сэргийлж эхэндээ бүх баганаар эхлүүлнэ
  const [visibleColumns, setVisibleColumns] = useState<string[]>(data.columns);
  const [showColumnDropdown, setShowColumnDropdown] = useState(false);

  // Client дээр ассаны дараа localStorage-оос уншиж тохируулна
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const valid = parsed.filter((c) => data.columns.includes(c));
          if (valid.length > 0) {
            setVisibleColumns(valid);
            return;
          }
        }
      }
    } catch (e) {
      // ignore
    }
    setVisibleColumns(data.columns);
  }, [storageKey, data.columns]);

  // Сонгогдсон багануудыг localStorage-д хадгалах
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(visibleColumns));
    } catch (e) {
      // ignore
    }
  }, [storageKey, visibleColumns]);

  const toggleColumn = (col: string) => {
    if (visibleColumns.includes(col)) {
      if (visibleColumns.length === 1) return; // Keep at least one column
      setVisibleColumns(visibleColumns.filter((c) => c !== col));
    } else {
      const updated = data.columns.filter((c) => visibleColumns.includes(c) || c === col);
      setVisibleColumns(updated);
    }
  };

  const href = (offset: number) => `/database?${new URLSearchParams({ table: data.table, ...(q ? { q } : {}), offset: String(offset) })}`;
  const from = data.total ? data.offset + 1 : 0;
  const to = Math.min(data.offset + data.page, data.total);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <form className="flex flex-1 flex-wrap items-center gap-2" action="/database">
          <input type="hidden" name="table" value={data.table} />
          <input
            name="q"
            defaultValue={q}
            placeholder="Хайх (текст баганаас)…"
            aria-label="Хайх"
            className="min-w-[220px] flex-1 rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none"
          />
          <button className="cursor-pointer rounded-[10px] border-[1.5px] border-line-2 px-4 py-2 text-sm font-semibold hover:border-brand">Хайх</button>
        </form>

        <div className="relative">
          <button
            type="button"
            onClick={() => setShowColumnDropdown(!showColumnDropdown)}
            className="cursor-pointer rounded-[10px] border-[1.5px] border-line-2 bg-panel px-3 py-2 text-sm font-semibold hover:border-brand"
          >
            Багана ({visibleColumns.length}/{data.columns.length})
          </button>
          {showColumnDropdown && (
            <div className="absolute right-0 z-20 mt-2 w-56 rounded-[12px] border border-line-2 bg-panel p-3 shadow-lg">
              <div className="mb-2 text-xs font-semibold text-muted uppercase">Багана сонгох</div>
              <div className="flex flex-col gap-1.5 max-h-60 overflow-y-auto">
                {data.columns.map((col) => {
                  const isChecked = visibleColumns.includes(col);
                  const isLast = visibleColumns.length === 1 && isChecked;
                  return (
                    <label
                      key={col}
                      className={`flex items-center gap-2 text-sm ${isLast ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:text-brand"}`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        disabled={isLast}
                        onChange={() => toggleColumn(col)}
                        className="size-4 accent-brand"
                      />
                      <span className="font-mono text-xs truncate">{col}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <span className="ml-auto font-mono text-[13px] text-muted">{from}–{to} / {data.total}</span>
      </div>

      <div className="overflow-x-auto rounded-[12px] border border-line">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-panel-2">
            <tr>
              {data.columns.map((c) =>
                visibleColumns.includes(c) ? (
                  <th key={c} className="whitespace-nowrap px-3 py-2 font-mono text-[11px] uppercase tracking-wider text-muted">
                    {c}
                  </th>
                ) : null
              )}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, i) => (
              <tr key={i} className="border-t border-line align-top">
                {row.map((v, j) =>
                  visibleColumns.includes(data.columns[j]) ? (
                    <td key={j} className="max-w-[420px] px-3 py-2">
                      <Cell column={data.columns[j]} value={v} />
                    </td>
                  ) : null
                )}
              </tr>
            ))}
            {!data.rows.length && (
              <tr>
                <td colSpan={visibleColumns.length} className="px-3 py-6 text-center text-muted">
                  Мөр алга
                </td>
              </tr>
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