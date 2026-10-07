import Link from "next/link";
import type { WeeklyReport } from "@/lib/types";

/** Самбар: энэ 7 хоногт хамгийн их асуусан сэдэв + хариулж чадаагүй давтагдсан асуулт */
export function TopTopics({ report }: { report: WeeklyReport }) {
  const max = Math.max(1, ...report.topics.map(([, n]) => n));
  return (
    <div className="grid gap-8 md:grid-cols-2">
      <div>
        <h3 className="mb-3 text-sm text-muted">Их асуусан сэдэв</h3>
        {report.topics.length ? report.topics.map(([label, n]) => (
          <div key={label} className="mb-2.5">
            <div className="flex justify-between gap-3 text-sm"><span className="truncate">{label}</span><span className="font-mono text-muted">{n}</span></div>
            <div className="mt-1 h-1 rounded-sm bg-line-2"><div className="h-full rounded-sm bg-brand" style={{ width: `${(100 * n) / max}%` }} /></div>
          </div>
        )) : <p className="text-sm text-muted">Энэ 7 хоногт асуулт алга.</p>}
      </div>
      <div>
        <h3 className="mb-3 text-sm text-muted">Хариулж чадаагүй (давтагдсан)</h3>
        {report.unanswered_top.length ? (
          <ul className="space-y-2 text-sm">
            {report.unanswered_top.map((x) => (
              <li key={x.q}>«{x.q}»{x.count > 1 && <span className="ml-1 font-mono text-warn">×{x.count}</span>}</li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted">Бүх асуултад хариулсан ✓</p>}
        <Link href="/unanswered" className="mt-3 inline-block text-sm text-brand hover:underline">Хариулт заах →</Link>
      </div>
    </div>
  );
}
