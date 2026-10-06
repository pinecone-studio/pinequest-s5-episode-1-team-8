"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { VoiceData } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function VoiceSettings({ initial }: { initial: VoiceData }) {
  const [speed, setSpeed] = useState(initial.settings.speed);
  const [pause, setPause] = useState(initial.settings.pause_ms);
  const [lexicon, setLexicon] = useState(initial.settings.lexicon);
  const { pending, error, message, run } = useAction();
  const setLex = (i: number, key: "word" | "say", value: string) => setLexicon((rows) => rows.map((r, n) => n === i ? { ...r, [key]: value } : r));
  return <div className="space-y-6">
    <div className="grid gap-4 rounded-xl border border-line bg-panel p-5 md:grid-cols-2">
      <label className="text-sm text-muted">Ярих хурд: <b className="text-fg">{speed}</b><input className="mt-3 w-full accent-brand" type="range" min="0.7" max="1.15" step="0.05" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} /></label>
      <label className="text-sm text-muted">Өгүүлбэрийн завсар: <b className="text-fg">{pause}мс</b><input className="mt-3 w-full accent-brand" type="range" min="100" max="1000" step="50" value={pause} onChange={(e) => setPause(Number(e.target.value))} /></label>
    </div>
    <div className="rounded-xl border border-line bg-panel p-5"><h2 className="mb-4 font-semibold">Дуудлагын толь</h2>
      <div className="space-y-2">{lexicon.map((row, i) => <div className="flex gap-2" key={i}><input className="w-1/3 rounded-lg border border-line-2 bg-bg px-3 py-2" placeholder="CV" value={row.word} onChange={(e) => setLex(i, "word", e.target.value)} /><span className="self-center text-muted">→</span><input className="flex-1 rounded-lg border border-line-2 bg-bg px-3 py-2" placeholder="си ви" value={row.say} onChange={(e) => setLex(i, "say", e.target.value)} /><button className="px-2 text-danger" onClick={() => setLexicon((rows) => rows.filter((_, n) => n !== i))}>×</button></div>)}</div>
      <div className="mt-4 flex gap-3"><Button onClick={() => setLexicon((rows) => [...rows, { word: "", say: "" }])}>+ Үг нэмэх</Button><Button variant="primary" disabled={pending} onClick={() => run(() => apiSend("/api/voice/settings", "PUT", { speed, pause_ms: pause, lexicon }), "Хоолойн тохиргоо хадгалагдлаа ✓")}>Хадгалах</Button></div>
    </div>
    <ActionStatus error={error} message={message} />
  </div>;
}
