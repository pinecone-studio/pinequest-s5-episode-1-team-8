import { formatDateTime } from "@/lib/format";
import type { LeadChange } from "@/lib/types";

const short = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)} ${iso.slice(11, 16)}`;

function describe(c: LeadChange) {
  if (c.field === "phone") return `Дугаар ${c.old ?? "—"} → ${c.new ?? "—"}`;
  if (c.field === "appointment") {
    if (!c.new) return `Цаг цуцалсан (${c.old ? short(c.old) : "—"})`;
    return c.old ? `Цаг ${short(c.old)} → ${short(c.new)}` : `Цаг товлосон ${short(c.new)}`;
  }
  return `${c.field}: ${c.old ?? "—"} → ${c.new ?? "—"}`;
}

/** Залгагч кодоороо утсаар хийсэн өөрчлөлтүүд (AI өөрөө бичсэн — ажилтан гараар хийх шаардлагагүй) */
export function LeadChanges({ changes }: { changes: LeadChange[] }) {
  if (!changes.length) return null;
  return (
    <ul className="mt-1.5 space-y-0.5 text-[13px] text-muted">
      {changes.slice(0, 3).map((c) => (
        <li key={c.id}>
          <span title={c.source === "ai" ? "Залгагч утсаар, AI өөрчилсөн" : "Вэбээр"}>{c.source === "ai" ? "🤖" : "✏️"}</span>{" "}
          {describe(c)} <span className="font-mono">· {formatDateTime(c.ts)}</span>
        </li>
      ))}
    </ul>
  );
}
