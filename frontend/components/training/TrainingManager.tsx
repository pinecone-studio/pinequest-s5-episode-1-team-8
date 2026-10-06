"use client";

import { useState, type FormEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { TrainingAnswers, TrainingStatus } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function TrainingManager({ initial, answers }: { initial: TrainingStatus; answers: TrainingAnswers }) {
  const [rows, setRows] = useState(initial.taught);
  const { pending, error, message, run } = useAction();
  const choices = [["FAQ", answers.faq], ["Мэдээлэл", answers.facts], ["Тусгай", answers.special]] as const;
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const data = new FormData(form);
    run(async () => { await apiSend("/api/train/examples", "POST", { q: data.get("q"), answer: data.get("answer") }); form.reset(); const next = await apiSend<TrainingStatus>("/api/train", "GET"); setRows(next.taught); }, "Сургалтын жишээ нэмэгдлээ ✓");
  }
  return <div className="space-y-6">
    <div className="grid gap-4 sm:grid-cols-3"><Stat label="Суурь жишээ" value={initial.seed} /><Stat label="Гараар заасан" value={rows.length} /><Stat label="Модел" value={initial.model ? "Бэлэн" : "Бэлдээгүй"} /></div>
    <form onSubmit={submit} className="rounded-xl border border-line bg-panel p-5"><h2 className="mb-4 font-semibold">Зөв хариулт заах</h2><div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]"><input name="q" required placeholder="Залгагчийн асуулт" className="rounded-lg border border-line-2 bg-bg px-3 py-2.5" /><select name="answer" required defaultValue="" className="rounded-lg border border-line-2 bg-bg px-3 py-2.5"><option value="" disabled>— зөв хариулт —</option>{choices.map(([label, list]) => <optgroup key={label} label={label}>{list.map((x) => <option key={x.value} value={x.value}>{x.title}</option>)}</optgroup>)}</select><Button variant="primary" disabled={pending}>Нэмэх</Button></div></form>
    <div className="rounded-xl border border-line bg-panel p-5"><h2 className="mb-3 font-semibold">Заасан жишээнүүд</h2>{rows.length ? <div className="divide-y divide-line">{rows.map((row) => <div key={row.i} className="flex items-center gap-3 py-3"><div className="flex-1"><p>{row.q}</p><span className="text-xs text-muted">{row.faq ? `FAQ: ${row.faq}` : row.fact ? row.fact : row.label}</span></div><Button className="text-danger" onClick={() => run(async () => { await apiSend(`/api/train/examples/${row.i}`, "DELETE"); setRows((all) => all.filter((x) => x.i !== row.i)); }, "Жишээ устлаа")}>Устгах</Button></div>)}</div> : <p className="text-muted">Гараар заасан жишээ алга.</p>}</div>
    <ActionStatus error={error} message={message} />
  </div>;
}
function Stat({ label, value }: { label: string; value: number | string }) { return <div className="rounded-xl border border-line bg-panel p-5"><div className="font-mono text-3xl font-semibold">{value}</div><div className="mt-1 text-sm text-muted">{label}</div></div>; }
