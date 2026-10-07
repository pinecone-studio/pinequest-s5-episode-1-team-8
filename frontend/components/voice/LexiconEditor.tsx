"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { VoiceData } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { IconButton } from "./IconButton";

/** "Дуудлагын толь" таб: буруу дуудагддаг үг, товчлолыг хэрхэн дуудахыг заана (CV -> си ви) */
export function LexiconEditor({ settings, onSaved }: { settings: VoiceData["settings"]; onSaved: () => Promise<void> }) {
  const [lexicon, setLexicon] = useState(settings.lexicon);
  const { pending, error, message, run } = useAction();

  const update = (index: number, patch: Partial<{ word: string; say: string }>) =>
    setLexicon((all) => all.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  function save() {
    void run(async () => {
      await apiSend("/api/voice/settings", "PUT", {
        lexicon: lexicon.filter((row) => row.word.trim() && row.say.trim()),
        speed: settings.speed, pause_ms: settings.pause_ms,            // ElevenLabs-д хамаарахгүй — хэвээр
      });
      await onSaved();
    }, "Хадгаллаа. Хэрэгжүүлэхийн тулд «Аудиог шинэчлэх» дарна уу ✓");
  }

  return (
    <section className="space-y-4">
      <p className="max-w-4xl leading-7 text-muted">
        Буруу дуудагддаг үг, товчлолыг хэрхэн дуудахыг заана (жишээ нь <b className="text-fg">CV → си ви</b>,{" "}
        <b className="text-fg">Mbank → эм банк</b>). Хадгалсны дараа «Аудиог шинэчлэх» дарахад зөвхөн тухайн үгтэй өгүүлбэрүүд
        ElevenLabs-аар дахин үүснэ.
      </p>
      <div className="rounded-[14px] bg-panel px-[22px] py-5">
        <div className="space-y-2">
          {lexicon.length ? lexicon.map((row, index) => (
            <div className="flex gap-2" key={index}>
              <input className="w-44 rounded-[10px] border border-line-2 bg-bg px-3 py-2" placeholder="CV" value={row.word}
                onChange={(e) => update(index, { word: e.target.value })} />
              <span className="self-center text-muted">→</span>
              <input className="min-w-0 flex-1 rounded-[10px] border border-line-2 bg-bg px-3 py-2" placeholder="си ви" value={row.say}
                onChange={(e) => update(index, { say: e.target.value })} />
              <IconButton label="Устгах" danger onClick={() => setLexicon((all) => all.filter((_, i) => i !== index))}>×</IconButton>
            </div>
          )) : <p className="text-muted">Одоогоор үг алга.</p>}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => setLexicon((all) => [...all, { word: "", say: "" }])}>+ Үг нэмэх</Button>
          <Button variant="primary" onClick={save} disabled={pending}>Хадгалах</Button>
          <ActionStatus error={error} message={message} />
        </div>
      </div>
    </section>
  );
}
