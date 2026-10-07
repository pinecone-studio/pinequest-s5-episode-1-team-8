"use client";

import { useRef, useState } from "react";
import { BuildPanel } from "@/components/knowledge/BuildPanel";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { EnglishData, EnglishPhrases } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const PHRASES: [keyof Omit<EnglishPhrases, "holds" | "lead">, string][] = [
  ["greeting_suffix", "Мэндчилгээний дараа"], ["repeat", "Ойлгоогүй үед"],
  ["error", "Олдоогүй үед (2 дахь удаа)"], ["mongolian_only", "Орчуулаагүй мэдээлэл асуухад"],
];
const LEAD: [string, string][] = [["ask_name_again", "Нэр асуух"], ["ask_phone", "Дугаар асуух"],
  ["readback", "Дугаар уншихын өмнө"], ["confirm", "Баталгаажуулах"], ["phone_retry", "Дугаар дахин асуух"],
  ["done", "Бүртгэсэн"], ["done_no_phone", "Дугааргүй бүртгэсэн"], ["declined", "Татгалзсан"]];

export function EnglishEditor({ initial }: { initial: EnglishData }) {
  const [enabled, setEnabled] = useState(initial.enabled);
  const [items, setItems] = useState(initial.items);
  const [phrases, setPhrases] = useState(initial.phrases);
  const [audioError, setAudioError] = useState("");
  const playing = useRef<HTMLAudioElement | null>(null);
  const { pending, error, message, run } = useAction();
  const translated = items.filter((item) => item.en.trim()).length;

  function save() {
    const answers = Object.fromEntries(items.filter((item) => item.en.trim()).map((item) => [item.hash, item.en]));
    const questions = Object.fromEntries(items.filter((item) => item.id).map((item) => [item.id!, item.questions_en]));
    void run(() => apiSend("/api/english", "PUT", { enabled, answers, questions, phrases }),
      "Хадгаллаа. Англи аудио бэлдэх дарна уу ✓");
  }

  function play(hash: string, phone = false) {
    setAudioError(""); playing.current?.pause();
    const audio = new Audio(`/api/english/audio/${hash}${phone ? "?phone=1" : ""}`);
    playing.current = audio;
    void audio.play().catch(() => setAudioError("Англи аудио алга. Эхлээд аудио бэлдэнэ үү."));
  }

  return (
    <div className="space-y-7">
      <section className="border-b border-line pb-8">
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex cursor-pointer items-center gap-3 font-semibold"><input className="size-5 accent-brand" type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />Англи горим идэвхтэй</label>
          <span className="ml-auto"><Tag tone={initial.built ? "ok" : "gray"}>{initial.built ? `Бэлдсэн ${formatDateTime(initial.built_at)}` : "Аудио бэлдээгүй"}</Tag></span>
        </div>
        <div className="mt-6 font-mono text-6xl font-bold">{translated}<span className="text-2xl font-normal text-muted"> / {items.length} хариулт орчуулгатай</span></div>
        <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full bg-brand" style={{ width: `${items.length ? translated / items.length * 100 : 0}%` }} /></div>
      </section>

      <section className="border-b border-line pb-8"><h2 className="font-semibold">Хэллэгүүд</h2>
        <div className="mt-5 rounded-[14px] bg-panel px-[22px] py-5">
          <div className="space-y-3">{PHRASES.map(([key, label]) => <label key={key} className="block text-sm text-muted">{label}<input className="mt-1.5 w-full rounded-[10px] border border-line-2 bg-bg px-3 py-2.5 text-fg" value={phrases[key]}
            onChange={(event) => setPhrases((current) => ({ ...current, [key]: event.target.value }))} /></label>)}</div>
          <label className="mt-3 block text-sm text-muted">Хүлээлгэх (мөр бүрд нэг)<textarea className="mt-1.5 min-h-20 w-full rounded-[10px] border border-line-2 bg-bg p-3 text-fg" value={phrases.holds.join("\n")}
            onChange={(event) => setPhrases((current) => ({ ...current, holds: event.target.value.split("\n") }))} /></label>
          <details className="mt-4"><summary className="cursor-pointer font-semibold">Бүртгэлийн хэллэгүүд</summary><div className="mt-4 space-y-3">{LEAD.map(([key, label]) => <label key={key} className="block text-sm text-muted">{label}<input className="mt-1.5 w-full rounded-[10px] border border-line-2 bg-bg px-3 py-2.5 text-fg" value={phrases.lead[key] || ""}
            onChange={(event) => setPhrases((current) => ({ ...current, lead: { ...current.lead, [key]: event.target.value } }))} /></label>)}</div></details>
        </div>
      </section>

      <section><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">Хариултууд</h2><Button variant="primary" onClick={save} disabled={pending}>Хадгалах</Button></div>
        <div className="overflow-hidden rounded-[14px] bg-panel px-[22px]">
          {items.map((row, index) => <div key={row.hash} className="grid gap-5 border-b border-line py-5 last:border-b-0 lg:grid-cols-[minmax(0,.85fr)_minmax(0,1.15fr)_auto]">
            <div><p className="leading-6">{row.mn}</p><div className="mt-2 flex flex-wrap gap-2 text-xs text-muted"><span>{row.kind === "faq" ? `FAQ ${row.id}` : "мэдээлэл"}</span>
              {!row.en ? <Tag tone="gray">орчуулаагүй</Tag> : !row.built ? <Tag tone="warn">аудио бэлдээгүй</Tag> : null}
              {row.flags.map((flag) => <Tag key={flag} tone="warn">⚠ {flag}</Tag>)}</div></div>
            <div><textarea className="min-h-20 w-full rounded-[10px] border border-line-2 bg-bg p-3" placeholder="English translation" value={row.en}
              onChange={(event) => setItems((all) => all.map((item, i) => i === index ? { ...item, en: event.target.value } : item))} />
              {row.id && <details className="mt-2"><summary className="cursor-pointer text-sm text-muted">Англи асуултууд ({row.questions_en.length})</summary><textarea className="mt-2 min-h-20 w-full rounded-[10px] border border-line-2 bg-bg p-3 text-sm" placeholder="How much does it cost?" value={row.questions_en.join("\n")}
                onChange={(event) => setItems((all) => all.map((item, i) => i === index ? { ...item, questions_en: event.target.value.split("\n") } : item))} /></details>}</div>
            <div className="flex gap-2">{row.built ? <><Button onClick={() => play(row.hash)}>▶</Button><Button onClick={() => play(row.hash, true)}>☎</Button></> : <Tag tone="gray">—</Tag>}</div>
          </div>)}
          {!items.length && <p className="py-10 text-center text-muted">Орчуулах хариулт алга.</p>}
        </div>
      </section>

      {initial.stale.length > 0 && <details className="rounded-[14px] bg-panel px-[22px] py-5"><summary className="cursor-pointer font-semibold">Хуучирсан орчуулгууд ({initial.stale.length})</summary><div className="mt-4 divide-y divide-line">{initial.stale.map((row) => <div key={row.hash} className="py-3"><p>{row.mn}</p><p className="mt-1 text-sm text-muted">{row.en}</p></div>)}</div></details>}
      <div className="flex flex-wrap items-center gap-3"><Button variant="primary" onClick={save} disabled={pending}>Хадгалах</Button><ActionStatus error={error || audioError} message={message} /></div>
      <BuildPanel startPath="/api/english/build" title="Англи аудио бэлдэх" buttonLabel="Англи аудио бэлдэх"
        description="Хадгалсан англи орчуулга, хэллэгүүдийг урьдчилан аудио болгож, утасны чанарын шалгалт хийнэ. Орчуулаагүй мэдээллийг AI англиар зохиож хэлэхгүй." />
    </div>
  );
}
