"use client";

import { useState } from "react";
import { BuildPanel } from "@/components/knowledge/BuildPanel";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import type { FaqData, FaqItem } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function FaqEditor({ initial }: { initial: FaqData }) {
  const [greeting, setGreeting] = useState(initial.greeting);
  const [items, setItems] = useState(initial.faq);
  const { pending, error, message, run } = useAction();
  const update = (index: number, patch: Partial<FaqItem>) =>
    setItems((rows) => rows.map((row, current) => current === index ? { ...row, ...patch } : row));

  function save() {
    const faq = items.map((row) => ({ ...row, id: row.id.trim(), answer: row.answer.trim(),
      questions: row.questions.map((question) => question.trim()).filter(Boolean) }))
      .filter((row) => row.id && row.answer && row.questions.length);
    void run(() => apiSend("/api/faq", "PUT", { ...initial, greeting: greeting.trim(), faq }),
      "Хадгаллаа. Аудио бэлдэх дарна уу ✓");
  }

  return (
    <div className="space-y-7">
      <div className="flex justify-end"><Button variant="primary" size="lg" onClick={save} disabled={pending}>Хадгалах</Button></div>
      <section className="rounded-[14px] bg-panel px-[22px] py-5">
        <label className="mb-2 block text-sm text-muted">Мэндчилгээ</label>
        <input className="w-full rounded-[10px] border border-line-2 bg-bg px-4 py-3 outline-none focus:border-brand"
          value={greeting} onChange={(event) => setGreeting(event.target.value)} />
        <div className="mt-6 divide-y divide-line">
          {items.map((item, index) => (
            <div key={`${item.id}-${index}`} className="py-5 first:pt-0">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <input className="w-[260px] rounded-[10px] border border-line-2 bg-bg px-3 py-2 font-mono text-sm outline-none focus:border-brand"
                  value={item.id} onChange={(event) => update(index, { id: event.target.value })} />
                {item.answer.includes("TODO") && <Tag tone="warn">TODO — алгасна</Tag>}
                {item.auto && <Tag tone="gray">автомат</Tag>}
                <Button className="ml-auto text-danger" onClick={() => setItems((rows) => rows.filter((_, i) => i !== index))}>Устгах</Button>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <label className="text-sm text-muted">Асуултууд (мөр бүрд нэг)
                  <textarea className="mt-2 min-h-32 w-full rounded-[10px] border border-line-2 bg-bg p-3 text-fg outline-none focus:border-brand"
                    value={item.questions.join("\n")} onChange={(event) => update(index, { questions: event.target.value.split("\n") })} />
                </label>
                <label className="text-sm text-muted">Хариулт
                  <textarea className="mt-2 min-h-32 w-full rounded-[10px] border border-line-2 bg-bg p-3 text-fg outline-none focus:border-brand"
                    value={item.answer} onChange={(event) => update(index, { answer: event.target.value })} />
                </label>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => setItems((rows) => [...rows, { id: `faq_${Date.now() % 100000}`, questions: [""], answer: "" }])}>+ FAQ нэмэх</Button>
          <Button variant="primary" onClick={save} disabled={pending}>Хадгалах</Button>
          <ActionStatus error={error} message={message} />
        </div>
      </section>
      <BuildPanel />
    </div>
  );
}
