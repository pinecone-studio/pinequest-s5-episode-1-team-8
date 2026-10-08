"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/PageHeader";
import { Td } from "@/components/ui/Table";
import { Tag } from "@/components/ui/Tag";
import { formatDateTime, formatSeconds } from "@/lib/format";
import type { Call } from "@/lib/types";

type SortField = "started_at" | "duration" | "unanswered";
type SortOrder = "asc" | "desc";

/** Дуудлагын хүснэгт. Мөр дээр дарахад тухайн дуудлагын яриа нээгдэнэ. */
export function CallsTable({ calls }: { calls: Call[] }) {
  const [sortField, setSortField] = useState<SortField>("started_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  }

  const sortedCalls = useMemo(() => {
    return [...calls].sort((a, b) => {
      let aVal: any = a[sortField];
      let bVal: any = b[sortField];

      if (sortField === "started_at") {
        aVal = new Date(a.started_at).getTime();
        bVal = new Date(b.started_at).getTime();
      }

      if (aVal < bVal) return sortOrder === "asc" ? -1 : 1;
      if (aVal > bVal) return sortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [calls, sortField, sortOrder]);

  if (!calls.length) return <EmptyState>Дуудлага алга. Zoiper-оос дотуур дугаар руу залгаж туршаарай.</EmptyState>;

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return "↕";
    return sortOrder === "asc" ? "↑" : "↓";
  };

  const getAriaSort = (field: SortField) => {
    if (sortField !== field) return "none";
    return sortOrder === "asc" ? "ascending" : "descending";
  };

  return (
    <>
      {/* Desktop Table View */}
      <div className="max-md:hidden overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-line-2 text-xs text-muted uppercase">
              <th className="py-3 px-4 font-semibold">
                <button
                  type="button"
                  onClick={() => handleSort("started_at")}
                  className="flex items-center gap-1.5 text-fg hover:text-brand cursor-pointer"
                  aria-sort={getAriaSort("started_at")}
                >
                  Хэзээ <span>{getSortIcon("started_at")}</span>
                </button>
              </th>
              <th className="py-3 px-4 font-semibold">Залгагч</th>
              <th className="py-3 px-4 font-semibold">
                <button
                  type="button"
                  onClick={() => handleSort("duration")}
                  className="flex items-center gap-1.5 text-fg hover:text-brand cursor-pointer"
                  aria-sort={getAriaSort("duration")}
                >
                  Үргэлжилсэн <span>{getSortIcon("duration")}</span>
                </button>
              </th>
              <th className="py-3 px-4 font-semibold">Асуулт</th>
              <th className="py-3 px-4 font-semibold">
                <button
                  type="button"
                  onClick={() => handleSort("unanswered")}
                  className="flex items-center gap-1.5 text-fg hover:text-brand cursor-pointer"
                  aria-sort={getAriaSort("unanswered")}
                >
                  Хариулж чадаагүй <span>{getSortIcon("unanswered")}</span>
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedCalls.map((c) => (
              <tr key={c.uuid} className="relative hover:bg-panel-2 border-b border-line-2/50">
                <Td className="font-mono text-sm py-3 px-4">
                  <Link href={`/calls/${c.uuid}`} className="after:absolute after:inset-0">
                    {formatDateTime(c.started_at)}
                  </Link>
                </Td>
                <Td className="py-3 px-4">{c.caller || "—"}</Td>
                <Td className="font-mono text-sm py-3 px-4">{formatSeconds(c.duration)}</Td>
                <Td className="font-mono text-sm py-3 px-4">{c.questions}</Td>
                <Td className="py-3 px-4">{c.unanswered ? <Tag tone="warn">{c.unanswered}</Tag> : <span className="font-mono text-sm">0</span>}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card View */}
      <div className="flex flex-col gap-3 md:hidden">
        {/* Mobile Sorting Controls */}
        <div className="flex items-center justify-between px-1 text-xs text-muted">
          <span>Эрэмбэлэх:</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleSort("started_at")}
              className={`underline-offset-4 hover:underline ${sortField === "started_at" ? "font-bold text-brand" : ""}`}
            >
              Огноо {sortField === "started_at" && (sortOrder === "asc" ? "↑" : "↓")}
            </button>
            <button
              type="button"
              onClick={() => handleSort("duration")}
              className={`underline-offset-4 hover:underline ${sortField === "duration" ? "font-bold text-brand" : ""}`}
            >
              Хугацаа {sortField === "duration" && (sortOrder === "asc" ? "↑" : "↓")}
            </button>
            <button
              type="button"
              onClick={() => handleSort("unanswered")}
              className={`underline-offset-4 hover:underline ${sortField === "unanswered" ? "font-bold text-brand" : ""}`}
            >
              Асуудал {sortField === "unanswered" && (sortOrder === "asc" ? "↑" : "↓")}
            </button>
          </div>
        </div>

        {sortedCalls.map((c) => (
          <Link
            key={c.uuid}
            href={`/calls/${c.uuid}`}
            className="relative flex flex-col gap-2 rounded-[12px] border border-line-2 bg-panel p-4 transition hover:border-brand"
          >
            <div className="flex items-center justify-between text-sm">
              <span className="font-mono font-medium text-fg">{formatDateTime(c.started_at)}</span>
              <span className="font-mono text-muted">{formatSeconds(c.duration)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted">Залгагч: <strong className="text-fg">{c.caller || "—"}</strong></span>
              <span className="text-muted">Асуулт: <strong className="font-mono text-fg">{c.questions}</strong></span>
            </div>
            {c.unanswered ? (
              <div className="mt-1 flex items-center justify-between border-t border-line-2 pt-2 text-xs">
                <span className="text-muted">Хариулж чадаагүй:</span>
                <Tag tone="warn">{c.unanswered}</Tag>
              </div>
            ) : null}
          </Link>
        ))}
      </div>
    </>
  );
}