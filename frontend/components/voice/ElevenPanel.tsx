"use client";

import { useCallback, useEffect, useState } from "react";
import { ActionStatus, Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import type { ElevenStatus } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { IconButton } from "./IconButton";

/** "Хоолой сонгох" таб (admin): ElevenLabs түлхүүр, хоолой сонгох, жишээ үүсгэж одоогийн аудиотой харьцуулах.
 *  ElevenLabs-ийг зөвхөн аудио БЭЛДЭХЭД ашиглана — дуудлагын үед бэлэн аудио тоглогдоно. */
export function ElevenPanel({ initial, play, onRebuild }: {
  initial: ElevenStatus;
  play: (url: string, phone?: boolean) => void;
  onRebuild: () => Promise<void>;
}) {
  const [data, setData] = useState(initial);
  const [voice, setVoice] = useState(initial.voice ?? "");
  const [showAll, setShowAll] = useState(false);
  const [key, setKey] = useState("");
  const { pending, error, message, run } = useAction();

  const refresh = useCallback(async () => setData(await apiSend<ElevenStatus>("/api/admin/eleven", "GET")), []);
  useEffect(() => {
    if (!data.job.running) return;
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [data.job.running, refresh]);

  const count = (id: string) => data.items.filter((i) => i.eleven.includes(id)).length;
  const voices = [...data.voices].sort((a, b) => count(b.id) - count(a.id)); // жишээтэй хоолой эхэнд
  const selected = voice || data.voice || voices[0]?.id || "";
  const selectedName = data.voices.find((v) => v.id === selected)?.name ?? "Сонгосон";
  const rows = data.items.filter((i) => showAll || i.sample || i.eleven.includes(selected))
    .sort((a, b) => Number(b.eleven.includes(selected)) - Number(a.eleven.includes(selected)));
  const missing = data.items.filter((i) => !i.recorded && !i.eleven.includes(selected));
  const missingChars = missing.reduce((sum, i) => sum + i.text.length, 0);
  const job = data.job;

  function saveKey() {
    void run(async () => {
      await apiSend("/api/admin/eleven/key", "POST", { key });
      setKey("");
      await refresh();
    }, "Түлхүүр хадгалагдлаа ✓");
  }

  function generate(scope: "sample" | "all") {
    if (scope === "all" && !window.confirm(`${missing.length} өгүүлбэр (~${missingChars} тэмдэгт) үүсгэнэ. ElevenLabs-ийн эрхээс хасагдана. Үргэлжлүүлэх үү?`)) return;
    void run(async () => {
      const next = await apiSend<ElevenStatus["job"]>("/api/admin/eleven/generate", "POST", { voice: selected, scope });
      setData((d) => ({ ...d, job: next }));
    }, "Үүсгэж эхэллээ…");
  }

  function choose() {
    void run(async () => {
      // SIM-TRUNK (Oron-гүй): өөрийн бичлэгээс бусад бүх өгүүлбэр сонгосон хоолойгоор
      const clips = Object.fromEntries(data.items.filter((i) => !i.recorded).map((i) => [i.hash, "eleven"]));
      const r = await apiSend<{ eleven: number }>("/api/admin/eleven/choice", "PUT", { voice: selected, clips });
      await refresh();
      if (window.confirm(`${r.eleven} өгүүлбэр ${selectedName} хоолойгоор тоглогдоно (өөрийн бичлэгээс бусад). Аудиог одоо шинэчлэх үү?`)) {
        await apiSend("/api/voice/rebuild", "POST");
      }
      await onRebuild();
    }, "Хоолой сонгогдлоо ✓");
  }

  const keyForm = (
    <div className="flex flex-wrap gap-2">
      <input type="password" autoComplete="off" placeholder="sk_..." value={key} onChange={(e) => setKey(e.target.value)}
        className="min-w-0 flex-1 rounded-[10px] border border-line-2 bg-bg px-3 py-2" />
      <Button variant="primary" onClick={saveKey} disabled={pending || !key.trim()}>Хадгалах</Button>
    </div>
  );

  if (!data.has_key) {
    return (
      <section className="rounded-[14px] bg-panel px-[22px] py-5">
        <h2 className="font-semibold">ElevenLabs түлхүүр</h2>
        <p className="mt-2 mb-4 text-sm leading-6 text-muted">
          elevenlabs.io → Developers → API Keys («Text to Speech» + «Voices: Read» эрх). Зөвхөн энэ серверт хадгалагдана,
          дахин харуулахгүй. Түлхүүргүй бол «Аудио бэлдэх» ажиллахгүй (Oron TTS ашиглахгүй).
        </p>
        {keyForm}
        <div className="mt-3 min-h-5"><ActionStatus error={error} message={message} /></div>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <p className="max-w-4xl leading-7 text-muted">
        Хоолойг сонгоод жишээ үүсгэж одоогийн аудиотой зэрэгцүүлж сонсоно (☎ = утсаар сонсогдох чанар). Таалагдвал «Энэ хоолойг
        ашиглах». Үүсгэсэн жишээг аудио бэлдэхэд шууд ашиглана — ElevenLabs-ийг дахин төлөхгүй.
        <span className="ml-2"><Tag tone="gray">{data.model}</Tag></span>
      </p>
      {data.error && <Alert>{data.error}</Alert>}
      <div className="rounded-[14px] bg-panel px-[22px] py-5">
        <label className="flex flex-wrap items-center gap-3 text-sm text-muted">
          Хоолой
          <select value={selected} onChange={(e) => setVoice(e.target.value)}
            className="min-w-0 flex-1 rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-base text-fg">
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {count(v.id) ? `✓ ${count(v.id)} жишээ · ` : ""}{v.name}{v.info ? ` — ${v.info}` : ""}
                {v.id === data.voice ? " (одоогийн)" : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => generate("sample")} disabled={pending || job.running || !selected}>8 жишээ үүсгэх</Button>
          <Button onClick={() => generate("all")} disabled={pending || job.running || !missing.length || !selected}>
            Бүгдийг үүсгэх ({missing.length} үлдсэн, ~{missingChars} тэмдэгт)
          </Button>
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
            <input type="checkbox" className="accent-brand" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
            Бүх өгүүлбэрийг харуулах ({data.items.length})
          </label>
          <Button variant="primary" className="ml-auto" onClick={choose} disabled={pending || job.running || !selected}>
            Энэ хоолойг ашиглах
          </Button>
        </div>
        <div className="mt-3 flex min-h-5 flex-wrap gap-4 text-sm">
          {job.running ? <span className="text-muted">Үүсгэж байна… {job.done}/{job.total}</span>
            : job.error ? <span className="text-danger">{job.error}</span>
            : job.total ? <span className="text-brand">✓ {job.done} өгүүлбэр үүслээ (~{job.chars} тэмдэгт)</span> : null}
          {!job.running && <ActionStatus error={error} message={message} />}
        </div>
      </div>

      <div className="overflow-hidden rounded-[14px] bg-panel px-[22px]">
        <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-6 border-b border-line py-3 text-xs text-muted">
          <span>Өгүүлбэр</span><span>Одоо</span><span className="w-[88px]">{selectedName}</span>
        </div>
        <div className="divide-y divide-line">
          {rows.map((item) => {
            const has = item.eleven.includes(selected);
            return (
              <div key={item.hash} className="grid grid-cols-[1fr_auto_auto] items-center gap-x-6 py-3">
                <div className="min-w-0"><p className="leading-6">{item.text}</p><p className="text-xs text-muted">{item.kind}</p></div>
                {item.recorded ? <span className="col-span-2"><Tag>Таны бичлэг тоглогдоно</Tag></span> : (
                  <>
                    <div className="flex gap-2">
                      <IconButton label="Одоогийн аудио" onClick={() => play(`/api/voice/audio/${item.hash}`)}>▶</IconButton>
                      <IconButton label="Одоогийн, утасны чанараар" onClick={() => play(`/api/voice/audio/${item.hash}`, true)}>☎</IconButton>
                    </div>
                    <div className="flex w-[88px] gap-2">
                      {has ? (
                        <>
                          <IconButton label={`${selectedName}`} onClick={() => play(`/api/admin/eleven/audio/${selected}/${item.hash}`)}>▶</IconButton>
                          <IconButton label={`${selectedName}, утасны чанараар`} onClick={() => play(`/api/admin/eleven/audio/${selected}/${item.hash}`, true)}>☎</IconButton>
                        </>
                      ) : <Tag tone="gray">үүсгээгүй</Tag>}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <details className="text-sm text-muted">
        <summary className="cursor-pointer hover:text-fg">ElevenLabs түлхүүр солих</summary>
        <div className="mt-3 max-w-xl">{keyForm}</div>
      </details>
    </section>
  );
}
