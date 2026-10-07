import { formatDateTime } from "@/lib/format";
import { LEAD_STATUS, type LeadChange, type Person, type RagHit } from "@/lib/types";

const FIELD: Record<string, string> = {
  name: "Нэр", phone: "Утас", appointment: "Уулзалт", status: "Төлөв", course: "Хөтөлбөр/эвент", attendance: "Ирэх эсэх",
};
const ICON: Record<string, string> = { staff: "🧑‍🏫", call: "📞", web: "✏️", ai: "🤖" };
const short = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)} ${iso.slice(11, 16)}`;

/** Баруун самбар: баталгаажсан хүний хувийн RAG (person_docs), сүүлийн хайлт, өгөгдлийн санд бичсэн */
export function RagPanel({ person, trace, changes, changed }: { person: Person | null; trace: RagHit[]; changes: LeadChange[]; changed: Set<string> }) {
  return (
    <div className="space-y-4">
      <section className="rounded-[14px] bg-panel px-5 py-4">
        <h3 className="mb-3 text-sm text-muted">Хувийн RAG <span className="text-dim">· receptionist.db · person_docs</span></h3>
        {person ? (
          <>
            <div className="mb-3 flex flex-wrap items-baseline gap-x-3">
              <b className="text-lg">{person.name || "—"}</b>
              <span className="font-mono text-sm text-muted">код {person.code}</span>
              <span className={`text-sm ${person.status === "canceled" ? "text-danger" : "text-brand"}`}>{LEAD_STATUS[person.status] ?? person.status}</span>
            </div>
            <ul className="space-y-1.5 text-sm">
              {person.docs.map((d) => (
                <li key={d.field} className={`rounded-lg px-2.5 py-1.5 ${changed.has(d.field) ? "bg-brand/12" : "bg-bg"}`}>
                  <span className="mr-2 font-mono text-[11px] uppercase text-dim">{FIELD[d.field] ?? d.field}</span>
                  {d.text}
                  {d.vector && <span className="ml-1.5 font-mono text-[11px] text-dim" title="Вектор DB-д хадгалагдсан">· вектор</span>}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-sm text-muted">Код баталгаажмагц тухайн хүний баримтууд энд харагдана. AI зөвхөн эдгээрээс хайна — бусдын мэдээлэл хайлтад орохгүй.</p>
        )}
      </section>

      <section className="rounded-[14px] bg-panel px-5 py-4">
        <h3 className="mb-3 text-sm text-muted">RAG хайлт <span className="text-dim">· сүүлийн асуулт</span></h3>
        {trace.length ? (
          <ul className="space-y-2 text-sm">
            {trace.map((h, i) => (
              <li key={`${h.key}-${i}`}>
                <div className="flex justify-between gap-3">
                  <span className={i === 0 ? "" : "text-muted"}>{h.text}</span>
                  <span className="font-mono text-[13px] text-muted">{h.score.toFixed(2)}</span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <div className="h-1 flex-1 rounded-sm bg-line-2">
                    <div className={`h-full rounded-sm ${i === 0 ? "bg-brand" : "bg-dim"}`} style={{ width: `${Math.min(100, Math.max(4, h.score * 80))}%` }} />
                  </div>
                  <span className="font-mono text-[11px] text-dim">{h.kind}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">Асуулт бичихэд AI ямар баримт олсон, оноо нь энд харагдана.</p>
        )}
      </section>

      <section className="rounded-[14px] bg-panel px-5 py-4">
        <h3 className="mb-3 text-sm text-muted">Өгөгдлийн санд бичсэн <span className="text-dim">· lead_changes</span></h3>
        {changes.length ? (
          <ul className="space-y-1.5 font-mono text-[13px]">
            {changes.map((c) => (
              <li key={c.id}>
                <span className="text-dim">{formatDateTime(c.ts)}</span> {ICON[c.source] ?? "🤖"} {FIELD[c.field] ?? c.field}:{" "}
                <span className="text-muted">{c.field === "appointment" && c.old ? short(c.old) : c.old ?? "—"}</span> →{" "}
                <span className="text-brand">{c.new === null ? "цуцалсан" : c.field === "appointment" ? short(c.new) : c.new === "canceled" ? "цуцалсан" : c.new}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">Баталгаажуулсан өөрчлөлт энд гарна (Бүртгэл хуудсанд ч харагдана).</p>
        )}
      </section>
    </div>
  );
}
