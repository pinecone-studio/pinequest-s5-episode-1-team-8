"use client";

import { useMemo, useRef, useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Tag } from "@/components/ui/Tag";
import { startRecording, toCleanWav } from "@/lib/audio";
import { apiSend } from "@/lib/client";
import type { VoiceItem } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { IconButton } from "./IconButton";

type Filter = "all" | "flag" | "top" | "rec";
type SpeechResult = { 0: { transcript: string } };
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: { results: ArrayLike<SpeechResult> }) => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

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
  const [customText, setCustomText] = useState("");
  const [customWav, setCustomWav] = useState<Blob | null>(null);
  const [customMessage, setCustomMessage] = useState("");
  
  const [dialogConfig, setDialogConfig] = useState<{
    open: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    danger: boolean;
    onConfirm: () => void;
  }>({
    open: false,
    title: "",
    description: "",
    confirmLabel: "Устгах",
    danger: true,
    onConfirm: () => {},
  });

  const stopRef = useRef<(() => Promise<Blob>) | null>(null);
  const speechRef = useRef<SpeechRecognitionLike | null>(null);
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
    setDialogConfig({
      open: true,
      title: "Өгүүлбэр дахин үүсгэх",
      description: "Энэ өгүүлбэрийг ElevenLabs-аар өөр хувилбараар дахин үүсгэх үү?",
      confirmLabel: "Дахин үүсгэх",
      danger: false,
      onConfirm: () => {
        setDialogConfig((prev) => ({ ...prev, open: false }));
        void run(async () => { await apiSend(`/api/voice/regenerate/${item.hash}`, "POST"); await onChange(); }, "Дахин үүсгэж байна…");
      },
    });
  }

  function deleteRecording(item: VoiceItem) {
    setDialogConfig({
      open: true,
      title: "Бичлэг устгах",
      description: "Энэ бичлэгийг устгаад ElevenLabs-ийн аудио руу буцах уу?",
      confirmLabel: "Устгах",
      danger: true,
      onConfirm: () => {
        setDialogConfig((prev) => ({ ...prev, open: false }));
        void run(async () => { await apiSend(`/api/voice/recording/${item.hash}`, "DELETE"); await onChange(); }, "Бичлэг устлаа");
      },
    });
  }

  async function toggleRecord(hash: string) {
    if (recording === hash && stopRef.current) {
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
    if (recording) return;
    void run(async () => {
      stopRef.current = (await startRecording()).stop;
      setRecording(hash);
    }, "Бичиж байна… уншаад ■ дарна");
  }

  async function toggleCustomRecord() {
    if (recording === "custom" && stopRef.current) {
      const stop = stopRef.current;
      stopRef.current = null;
      speechRef.current?.stop();
      speechRef.current = null;
      setRecording(null);
      try {
        const { wav, seconds } = await toCleanWav(await stop());
        setCustomWav(wav);
        setCustomMessage(`${seconds.toFixed(1)} секунд бичлээ. Текстээ шалгаад хадгална уу.`);
      } catch (err) {
        setCustomMessage((err as Error).message);
      }
      return;
    }
    if (recording) return;
    setCustomText("");
    setCustomWav(null);
    setCustomMessage("");
    try {
      stopRef.current = (await startRecording()).stop;
      setRecording("custom");
      const browser = window as unknown as { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
      const Recognition = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
      if (!Recognition) {
        setCustomMessage("Энэ хөтөч яриа танихгүй байна. Бичвэрээ гараар оруулна уу.");
        return;
      }
      const speech = new Recognition();
      speech.lang = "mn-MN";
      speech.continuous = true;
      speech.interimResults = true;
      speech.onresult = (event) => {
        let text = "";
        for (let i = 0; i < event.results.length; i++) text += event.results[i][0].transcript;
        setCustomText(text.trim());
      };
      speech.onerror = () => setCustomMessage("Яриа танигдсангүй. Бичвэрээ гараар оруулж болно.");
      speech.start();
      speechRef.current = speech;
      setCustomMessage("Бичиж, монгол текст болгож байна…");
    } catch (err) {
      setCustomMessage((err as Error).message);
    }
  }

  function saveCustom() {
    if (!customWav || !customText.trim()) {
      setCustomMessage("Бичлэг болон монгол бичвэрээ оруулна уу.");
      return;
    }
    void run(async () => {
      const form = new FormData();
      form.append("file", customWav, "my-voice.wav");
      form.append("text", customText.trim());
      await apiSend("/api/voice/custom", "POST", form);
      setCustomText("");
      setCustomWav(null);
      setCustomMessage("");
      await onChange();
    }, "Таны бичлэг хадгалагдлаа ✓");
  }

  return (
    <section className="space-y-4">
      <div className="rounded-[14px] border border-line-2 bg-panel p-5">
        <h2 className="font-semibold">Өөрийн хоолойг бичиж, текст болгох</h2>
        <p className="mt-1 text-sm text-muted">Дуу бичихэд таны хэлсэн монгол текст доор гарна. Текстээ шалгаад хадгалсны дараа тухайн мөрийн ▶ товчоор аудиогоо сонсоно.</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant={recording === "custom" ? "primary" : "ghost"} disabled={pending || (Boolean(recording) && recording !== "custom")}
            onClick={() => void toggleCustomRecord()}>
            {recording === "custom" ? "■ Зогсоох" : "● Дуу бичих"}
          </Button>
          {customWav && <Button variant="primary" disabled={pending || !customText.trim()} onClick={saveCustom}>Бичлэгтэй нь хадгалах</Button>}
          {customMessage && <span className="text-sm text-muted">{customMessage}</span>}
        </div>
        <textarea rows={2} value={customText} onChange={(event) => setCustomText(event.target.value)}
          placeholder="Танигдсан монгол текст энд гарна. Шаардлагатай бол засна уу."
          className="mt-3 w-full rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-sm outline-none focus:border-brand" />
      </div>
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

      <ConfirmDialog
        open={dialogConfig.open}
        title={dialogConfig.title}
        description={dialogConfig.description}
        confirmLabel={dialogConfig.confirmLabel}
        cancelLabel="Цуцлах"
        danger={dialogConfig.danger}
        pending={pending}
        onConfirm={dialogConfig.onConfirm}
        onCancel={() => setDialogConfig((prev) => ({ ...prev, open: false }))}
      />
    </section>
  );
}