import Link from "next/link";
import type { RagStats } from "@/lib/types";

function Item({ value, label, href }: { value: number | string; label: string; href?: string }) {
  const body = (
    <>
      <div className="font-mono text-2xl font-bold">{value}</div>
      <div className="text-[13px] text-muted">{label}</div>
    </>
  );
  return href ? <Link href={href} className="hover:text-brand">{body}</Link> : <div>{body}</div>;
}

/** Самбар: бүх өгөгдөл нэг SQLite-д — байгууллагын RAG, хувийн RAG, дуудлага, бүртгэл */
export function RagStore({ rag }: { rag: RagStats }) {
  const kb = `${Math.max(1, Math.round(rag.db_bytes / 1024))} KB`;
  return (
    <div className="grid gap-6 md:grid-cols-[1fr_1fr_1fr]">
      <div>
        <h3 className="mb-3 text-sm text-muted">Байгууллагын RAG <span className="text-dim">· бүх залгагчид</span></h3>
        <div className="grid grid-cols-3 gap-3">
          <Item value={rag.facts} label="мэдээллийн өгүүлбэр" href="/knowledge" />
          <Item value={rag.faq_questions} label="FAQ асуулт" href="/faq" />
          <Item value={rag.chunks} label="том хэсэг" />
        </div>
      </div>
      <div>
        <h3 className="mb-3 text-sm text-muted">Хувийн RAG <span className="text-dim">· кодоор баталгаажсан хүн</span></h3>
        <div className="grid grid-cols-3 gap-3">
          <Item value={rag.people} label="кодтой хүн" href="/leads" />
          <Item value={rag.person_docs} label="хувийн баримт" />
          <Item value={rag.changes} label="утсаар өөрчилсөн" href="/leads" />
        </div>
      </div>
      <div>
        <h3 className="mb-3 text-sm text-muted">Дуудлага</h3>
        <div className="grid grid-cols-3 gap-3">
          <Item value={rag.calls} label="дуудлага" href="/calls" />
          <Item value={rag.messages} label="мессеж" />
          <Item value={rag.leads} label="бүртгэл" href="/leads" />
        </div>
      </div>
      <p className="text-[13px] leading-5 text-muted md:col-span-3">
        Бүгд нэг өгөгдлийн санд: <span className="font-mono text-fg">data/receptionist.db</span> (SQLite, {kb}) ·
        вектор {rag.embed_model ?? "bge-m3"}{rag.dim ? ` · ${rag.dim} хэмжээс` : ""}. Утасны AI асахдаа санах ойд ачаалж
        хайна (1мс-ээс бага), өөрчлөлтийг шууд энд бичнэ.
      </p>
    </div>
  );
}
