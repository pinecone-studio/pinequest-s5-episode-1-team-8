"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { FaqData, FaqItem } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function FaqEditor({ initial }: { initial: FaqData }) {
  const [greeting, setGreeting] = useState(initial.greeting);
  const [items, setItems] = useState(initial.faq);
  const { pending, error, message, run } = useAction();
  const update = (i: number, patch: Partial<FaqItem>) => setItems((rows) => rows.map((row, n) => n === i ? { ...row, ...patch } : row));

  function save() {
    run(() => apiSend("/api/faq", "PUT", { ...initial, greeting, faq: items }), "FAQ хадгалагдлаа ✓");
  }

  return (
    <div className="space-y-5">
      <div><label className="mb-2 block text-sm text-muted">Мэндчилгээ</label><textarea className="min-h-24 w-full rounded-xl border border-line-2 bg-panel p-4 outline-none focus:border-brand" value={greeting} onChange={(e) => setGreeting(e.target.value)} /></div>
      {items.map((item, i) => (
        <div key={`${item.id}-${i}`} className="rounded-xl border border-line bg-panel p-4">
          <div className="mb-3 flex gap-3"><input className="min-w-0 flex-1 rounded-lg border border-line-2 bg-bg px-3 py-2 font-mono text-sm outline-none focus:border-brand" value={item.id} onChange={(e) => update(i, { id: e.target.value })} /><Button className="text-danger" onClick={() => setItems((rows) => rows.filter((_, n) => n !== i))}>Устгах</Button></div>
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="text-sm text-muted">Асуултууд (мөр бүрд нэг)<textarea className="mt-2 min-h-32 w-full rounded-lg border border-line-2 bg-bg p-3 text-fg outline-none focus:border-brand" value={item.questions.join("\n")} onChange={(e) => update(i, { questions: e.target.value.split("\n") })} /></label>
            <label className="text-sm text-muted">Хариулт<textarea className="mt-2 min-h-32 w-full rounded-lg border border-line-2 bg-bg p-3 text-fg outline-none focus:border-brand" value={item.answer} onChange={(e) => update(i, { answer: e.target.value })} /></label>
          </div>
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-3"><Button onClick={() => setItems((rows) => [...rows, { id: `faq_${Date.now()}`, questions: [""], answer: "" }])}>+ FAQ нэмэх</Button><Button variant="primary" onClick={save} disabled={pending}>Хадгалах</Button><ActionStatus error={error} message={message} /></div>
    </div>
  );
}
