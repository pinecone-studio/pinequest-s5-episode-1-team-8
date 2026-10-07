import { formatDateTime } from "@/lib/format";
import { LEAD_STATUS, type LeadChange, type LeadStatus } from "@/lib/types";

const SOURCE: Record<LeadChange["source"], [string, string]> = {
  ai: ["🤖", "Залгагч өөрөө утсаар, AI өөрчилсөн"],
  staff: ["🧑‍🏫", "Ажилтан утсаар, AI өөрчилсөн"],
  web: ["✏️", "Вэбээр"],
  call: ["📞", "AI сануулгын дуудлагаар асуусан"],
};
const short = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)} ${iso.slice(11, 16)}`;

function describe(c: LeadChange) {
  if (c.field === "phone") return `Дугаар ${c.old ?? "—"} → ${c.new ?? "—"}`;
  if (c.field === "appointment") {
    if (!c.new) return `Цаг цуцалсан (${c.old ? short(c.old) : "—"})`;
    return c.old ? `Цаг ${short(c.old)} → ${short(c.new)}` : `Цаг товлосон ${short(c.new)}`;
  }
  if (c.field === "attendance") return c.new === "ирнэ" ? "Эвентэд ирнэ гэж баталсан" : "Эвентэд ирэхгүй";
  if (c.field === "status") {
    const label = (v: string | null) => (v ? LEAD_STATUS[v as LeadStatus] ?? v : "—");
    return c.new === "canceled" ? "Бүртгэл цуцалсан" : `Төлөв ${label(c.old)} → ${label(c.new)}`;
  }
  return `${c.field}: ${c.old ?? "—"} → ${c.new ?? "—"}`;
}

/** Утсаар хийсэн өөрчлөлтүүд: залгагч өөрийн кодоор, ажилтан ажилтны кодоор (AI өөрөө бичнэ — гараар хийхгүй) */
export function LeadChanges({ changes }: { changes: LeadChange[] }) {
  if (!changes.length) return null;
  return (
    <ul className="mt-1.5 space-y-0.5 text-[13px] text-muted">
      {changes.slice(0, 3).map((c) => (
        <li key={c.id}>
          <span title={SOURCE[c.source][1]}>{SOURCE[c.source][0]}</span>{" "}
          {describe(c)} <span className="font-mono">· {formatDateTime(c.ts)}</span>
        </li>
      ))}
    </ul>
  );
}
