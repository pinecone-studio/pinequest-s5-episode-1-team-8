import Link from "next/link";
import { EmptyState } from "@/components/PageHeader";
import { Tag } from "@/components/ui/Tag";
import { formatDateTime, formatSeconds } from "@/lib/format";
import type { Call } from "@/lib/types";

const TH = "border-b border-line-2 px-2.5 py-2.5 text-left font-mono text-[11px] font-medium tracking-[.1em] text-muted uppercase";
const TD = "border-b border-line px-2.5 py-3 align-top";

/** Дуудлагын хүснэгт. Мөр дээр дарахад тухайн дуудлагын яриа нээгдэнэ. */
export function CallsTable({ calls }: { calls: Call[] }) {
  if (!calls.length) return <EmptyState>Дуудлага алга. Zoiper-оос дотуур дугаар руу залгаж туршаарай.</EmptyState>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className={TH}>Хэзээ</th>
            <th className={TH}>Залгагч</th>
            <th className={TH}>Үргэлжилсэн</th>
            <th className={TH}>Асуулт</th>
            <th className={TH}>Хариулж чадаагүй</th>
          </tr>
        </thead>
        <tbody>
          {calls.map((c) => (
            <tr key={c.uuid} className="relative hover:bg-panel-2 [&:last-child>td]:border-b-0">
              <td className={`${TD} font-mono text-sm`}>
                {/* мөр бүхэлдээ дарагдана (after: бүх мөрийг бүрхэнэ) */}
                <Link href={`/calls/${c.uuid}`} className="after:absolute after:inset-0">
                  {formatDateTime(c.started_at)}
                </Link>
              </td>
              <td className={TD}>{c.caller || "—"}</td>
              <td className={`${TD} font-mono text-sm`}>{formatSeconds(c.duration)}</td>
              <td className={`${TD} font-mono text-sm`}>{c.questions}</td>
              <td className={TD}>{c.unanswered ? <Tag tone="warn">{c.unanswered}</Tag> : <span className="font-mono text-sm">0</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
