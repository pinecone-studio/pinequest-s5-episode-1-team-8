"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { EnglishData } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function EnglishEditor({ initial }: { initial: EnglishData }) {
  const [enabled, setEnabled] = useState(initial.enabled);
  const [items, setItems] = useState(initial.items);
  const [phrases, setPhrases] = useState(initial.phrases);
  const { pending, error, message, run } = useAction();
  const translated = items.filter((x) => x.en.trim()).length;
  function save() {
    const answers = Object.fromEntries(items.filter((x) => x.en.trim()).map((x) => [x.hash, x.en]));
    const questions = Object.fromEntries(items.filter((x) => x.id).map((x) => [x.id!, x.questions_en]));
    run(() => apiSend("/api/english", "PUT", { enabled, answers, questions, phrases }), "Англи хэлний тохиргоо хадгалагдлаа ✓");
  }
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-panel p-5"><label className="flex cursor-pointer items-center gap-3 font-semibold"><input className="size-5 accent-brand" type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />Англи горим идэвхтэй</label><span className="ml-auto font-mono text-brand">{translated}/{items.length} орчуулгатай</span></div>
    <div className="rounded-xl border border-line bg-panel p-5"><h2 className="mb-4 font-semibold">Системийн хэллэгүүд</h2><div className="grid gap-3">{Object.entries(phrases).map(([key, value]) => <label key={key} className="text-xs text-muted">{key}<input className="mt-1 w-full rounded-lg border border-line-2 bg-bg px-3 py-2 text-sm text-fg" value={value} onChange={(e) => setPhrases((p) => ({ ...p, [key]: e.target.value }))} /></label>)}</div></div>
    <div className="space-y-3">{items.map((row, i) => <div key={row.hash} className="grid gap-4 rounded-xl border border-line bg-panel p-4 lg:grid-cols-2"><div><p>{row.mn}</p><span className="text-xs text-muted">{row.kind}{row.id ? ` · ${row.id}` : ""}</span></div><div><textarea className="min-h-24 w-full rounded-lg border border-line-2 bg-bg p-3" placeholder="English translation" value={row.en} onChange={(e) => setItems((all) => all.map((x, n) => n === i ? { ...x, en: e.target.value } : x))} />{row.id && <textarea className="mt-2 min-h-16 w-full rounded-lg border border-line-2 bg-bg p-3 text-sm" placeholder="English questions, one per line" value={row.questions_en.join("\n")} onChange={(e) => setItems((all) => all.map((x, n) => n === i ? { ...x, questions_en: e.target.value.split("\n") } : x))} />}</div></div>)}</div>
    <div className="flex items-center gap-3"><Button variant="primary" onClick={save} disabled={pending}>Хадгалах</Button><ActionStatus error={error} message={message} /></div>
  </div>;
}
