"use client";

import { useMemo, useRef, useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { startRecording, toCleanWav } from "@/lib/audio";
import { apiSend } from "@/lib/client";
import type { VoiceItem } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { IconButton } from "./IconButton";

type Filter = "all" | "flag" | "top" | "rec";

/** "Өгүүлбэрүүд" таб: залгагчид тоглогдох бүх өгүүлбэр — сонсох, өөрөө бичих, ElevenLabs-аар дахин үүсгэх */
export function ClipList({ items, voiceName, play, onChange }: {
  items: VoiceItem[];
  voiceName: string;
  play: (url: string, phone?: boolean) => void;
  onChange: () => Promise<void>;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [recording, setRecording] = useState<string | null>(null);
  const stopRef = useRef<(() => Promise<Blob>) | null>(null);
  const { pending, error, message, run } = useAction();

  const top = useMemo(() => new Set(items.filter((i) => i.plays > 0).sort((a, b) => b.plays - a.plays)
    .slice(0, 10).map((i) => i.hash)), [items]);
  const filters: [Filter, string, (i: VoiceItem) => boolean][] = [
    ["all", "Бүгд", () => true],
    ["flag", "⚠ Шалгах", (i) => i.flags.length > 0 && !i.recorded],
    ["top", "Их тоглогддог", (i) => top.has(i.hash)],
    ["rec", "Бичлэг", (i) => i.recorded],
  ];
  const test = filters.find(([key]) => key === filter)![2];
  const q = search.trim().toLowerCase();
  let shown = items.filter(test).filter((i) => !q || i.text.toLowerCase().includes(q) || i.kind.toLowerCase().includes(q));
  if (filter === "top") shown = [...shown].sort((a, b) => b.plays - a.plays);

  function regenerate(item: VoiceItem) {
    if (!window.confirm("Энэ өгүүлбэрийг ElevenLabs-аар өөр хувилбараар дахин үүсгэх үү?")) return;
    void run(async () => { await apiSend(`/api/voice/regenerate/${item.hash}`, "POST"); await onChange(); }, "Дахин үүсгэж байна…");
  }

  function deleteRecording(item: VoiceItem) {
    if (!window.confirm("Энэ бичлэгийг устгаад ElevenLabs-ийн аудио руу буцах уу?")) return;
    void run(async () => { await apiSend(`/api/voice/recording/${item.hash}`, "DELETE"); await onChange(); }, "Бичлэг устлаа");
  }

  async function toggleRecord(hash: string) {
    if (recording === hash && stopRef.current) {          // зогсоох -> цэвэрлээд хадгалах
      const stop = stopRef.current;
      stopRef.current = null;
      setRecording(null);
      const blob = await stop();
      void run(async () => {
        const { wav } = await toCleanWav(blob);
        const form = new FormData();
        form.append("file", wav, `${hash}.wav`);
        await apiSend(`/api/voice/recording/${hash}`, "POST", form);
        await onChange();
      }, "Бичлэг хадгалагдлаа ✓ «Аудиог шинэчлэх» дарвал залгагчид сонсогдоно");
      return;
    }
    if (recording) return;                                  // нэг удаа нэг өгүүлбэр
    void run(async () => {
      stopRef.current = (await startRecording()).stop;
      setRecording(hash);
    }, "Бичиж байна… уншаад ■ дарна");
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {filters.map(([key, label, f]) => (
          <Button key={key} variant={filter === key ? "primary" : "ghost"} onClick={() => setFilter(key)}>
            {label} ({items.filter(f).length})
          </Button>
        ))}
        <input className="ml-auto w-52 rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-sm" placeholder="Хайх…"
          value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <p className="text-sm text-muted">
        ▶ сонсох · ☎ утсаар сонсогдох чанар · ● өөрийн хоолойгоор бичих (ElevenLabs-ийн оронд тоглогдоно) · ↻ өөр хувилбараар
        дахин үүсгэх. Чанарын шалгалт аудио бэлдэх бүрт автоматаар ажиллана.
      </p>
      <div className="min-h-5"><ActionStatus error={error} message={message} /></div>
      <div className="overflow-hidden rounded-[14px] bg-panel px-[22px]">
        {shown.length ? (
          <div className="divide-y divide-line">
            {shown.map((item) => (
              <div key={item.hash} className="flex items-center gap-4 py-4 max-md:flex-wrap">
                <div className="flex shrink-0 gap-2">
                  <IconButton label="Сонсох" onClick={() => play(`/api/voice/audio/${item.hash}`)}>▶</IconButton>
                  <IconButton label="Утасны чанараар" onClick={() => play(`/api/voice/audio/${item.hash}`, true)}>☎</IconButton>
                  <IconButton label="Өөрөө бичих" danger active={recording === item.hash} disabled={pending && recording !== item.hash}
                    onClick={() => void toggleRecord(item.hash)}>{recording === item.hash ? "■" : "●"}</IconButton>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="leading-6">{item.text}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <span>{item.kind}{item.plays ? ` · ${item.plays} удаа тоглогдсон` : ""}</span>
                    {top.has(item.hash) && <Tag>Их тоглогддог</Tag>}
                    {!item.recorded && item.flags.map((flag) => (
                      <span key={flag} title={item.hyp ? `Яриа таних сонссон: ${item.hyp}` : undefined}><Tag tone="warn">⚠ {flag}</Tag></span>
                    ))}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {item.recorded ? (
                    <><Tag>Бичлэг</Tag><IconButton label="Бичлэг устгах" danger onClick={() => deleteRecording(item)}>×</IconButton></>
                  ) : (
                    <><Tag tone="gray">Eleven · {voiceName}{item.seed ? ` #${item.seed + 1}` : ""}</Tag>
                      <IconButton label="Дахин үүсгэх" disabled={pending} onClick={() => regenerate(item)}>↻</IconButton></>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : <p className="py-10 text-center text-muted">Алга ✓</p>}
      </div>
    </section>
  );
}
