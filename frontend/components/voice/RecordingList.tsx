"use client";

import { useRef, useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { startRecording, toCleanWav } from "@/lib/audio";
import { apiSend } from "@/lib/client";
import type { VoiceItem } from "@/lib/types";

type RowState = { error?: string; message?: string; busy?: boolean };

/** Өгүүлбэр бүрийг өөрийн хоолойгоор: микрофоноор бичих эсвэл аудио файл оруулах, сонсох, устгах.
 *  Бичлэгтэй өгүүлбэрт "Бэлдэх" үед TTS хийхгүй — утсаар таны хоолой сонсогдоно. */
export function RecordingList({ items }: { items: VoiceItem[] }) {
  const [recorded, setRecorded] = useState<Record<string, boolean>>(() => Object.fromEntries(items.map((x) => [x.hash, x.recorded])));
  const [rows, setRows] = useState<Record<string, RowState>>({});
  const [filter, setFilter] = useState<"all" | "todo">("all");
  const [recording, setRecording] = useState<string | null>(null);
  const stopRef = useRef<(() => Promise<Blob>) | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const setRow = (h: string, state: RowState) => setRows((r) => ({ ...r, [h]: state }));
  const done = items.filter((x) => recorded[x.hash]).length;
  const shown = filter === "todo" ? items.filter((x) => !recorded[x.hash]) : items;

  async function save(h: string, blob: Blob) {
    setRow(h, { busy: true });
    try {
      const { wav, seconds } = await toCleanWav(blob);
      const form = new FormData();
      form.append("file", wav, `${h}.wav`);
      await apiSend(`/api/voice/${h}`, "POST", form);
      setRecorded((r) => ({ ...r, [h]: true }));
      setRow(h, { message: `Хадгаллаа ✓ (${seconds.toFixed(1)}с)` });
    } catch (err) {
      setRow(h, { error: (err as Error).message });
    }
  }

  async function toggleRecord(h: string) {
    if (recording === h && stopRef.current) {     // зогсоох -> хадгалах
      const stop = stopRef.current;
      stopRef.current = null;
      setRecording(null);
      await save(h, await stop());
      return;
    }
    if (recording) return;                         // нэг удаа нэг өгүүлбэр
    try {
      stopRef.current = (await startRecording()).stop;
      setRecording(h);
      setRow(h, { message: "Бичиж байна… уншаад «Зогсоох» дарна" });
    } catch (err) {
      setRow(h, { error: (err as Error).message });
    }
  }

  function play(h: string) {
    audioRef.current?.pause();
    const audio = new Audio(`/api/voice/${h}/audio?t=${Date.now()}`);
    audioRef.current = audio;
    audio.onerror = () => setRow(h, { error: "Аудио алга — бичээгүй эсвэл «Бэлдэх» хийгээгүй байна" });
    void audio.play().catch(() => undefined);
  }

  async function remove(h: string) {
    setRow(h, { busy: true });
    try {
      await apiSend(`/api/voice/${h}`, "DELETE");
      setRecorded((r) => ({ ...r, [h]: false }));
      setRow(h, { message: "Устгалаа — TTS хоолой руу буцлаа" });
    } catch (err) {
      setRow(h, { error: (err as Error).message });
    }
  }

  return (
    <div className="rounded-xl border border-line bg-panel p-5">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h2 className="flex-1 font-semibold">
          Өөрийн хоолойгоор · <span className="font-mono text-brand">{done}</span>
          <span className="font-mono text-muted"> / {items.length}</span> бичсэн
        </h2>
        <div className="flex gap-1.5" role="group" aria-label="Шүүлтүүр">
          {(["all", "todo"] as const).map((f) => (
            <Button key={f} type="button" onClick={() => setFilter(f)} className={filter === f ? "border-brand text-brand" : ""}>
              {f === "all" ? "Бүгд" : "Бичээгүй"}
            </Button>
          ))}
        </div>
      </div>
      <p className="mb-4 text-sm text-muted">
        Өгүүлбэр бүрийг тайван, тод уншаад бичнэ (эсвэл бэлэн аудио файл оруулна). Чимээгүйг автоматаар тайрна.
        «Бэлдэх» дарсны дараа утсаар TTS-ийн оронд таны хоолой сонсогдоно. Текст өөрчлөгдвөл дахин бичнэ.
      </p>
      <div className="max-h-[560px] divide-y divide-line overflow-auto">
        {shown.map((row) => {
          const state = rows[row.hash] ?? {};
          const isRec = recording === row.hash;
          return (
            <div key={row.hash} className="flex flex-wrap items-start gap-3 py-3">
              <div className="min-w-[240px] flex-1">
                <p>{row.text}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                  {row.kind}
                  {recorded[row.hash] ? <Tag>Бичлэг ✓</Tag> : <Tag tone="gray">TTS</Tag>}
                  <ActionStatus error={state.error} message={state.message} />
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Button type="button" onClick={() => toggleRecord(row.hash)} disabled={state.busy || (Boolean(recording) && !isRec)}
                  className={isRec ? "border-danger bg-danger text-white hover:border-danger" : "text-danger"}>
                  {isRec ? "■ Зогсоох" : "● Бичих"}
                </Button>
                <label className={`inline-flex cursor-pointer items-center rounded-[10px] border-[1.5px] border-dashed border-line-2 px-3 text-sm font-semibold text-muted hover:border-brand hover:text-fg ${state.busy || recording ? "pointer-events-none opacity-45" : ""}`}>
                  ↑ Файл
                  <input type="file" accept="audio/*" className="sr-only" aria-label={`«${row.text.slice(0, 30)}» — аудио файл`}
                    onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void save(row.hash, f); }} />
                </label>
                <Button type="button" onClick={() => play(row.hash)} aria-label="Сонсох">▶</Button>
                {recorded[row.hash] && (
                  <Button type="button" onClick={() => remove(row.hash)} disabled={state.busy} className="text-danger">Устгах</Button>
                )}
              </div>
            </div>
          );
        })}
        {!shown.length && <p className="py-8 text-center text-muted">{filter === "todo" ? "Бүгдийг бичсэн 🎉" : "Өгүүлбэр алга"}</p>}
      </div>
    </div>
  );
}
