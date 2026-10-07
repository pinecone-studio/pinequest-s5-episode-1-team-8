"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { BuildPanel } from "@/components/knowledge/BuildPanel";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { ReferenceVoice, VoiceData, VoiceItem } from "@/lib/types";
import { useAction } from "@/lib/useAction";

type Filter = "all" | "flag" | "top";
type Recorder = { ctx: AudioContext; stream: MediaStream; node: ScriptProcessorNode; chunks: Float32Array[]; hash: string };

export function VoiceSettings({ initial, initialReference = null }: { initial: VoiceData; initialReference?: ReferenceVoice | null }) {
  const [data, setData] = useState(initial);
  const [reference, setReference] = useState(initialReference);
  const [filter, setFilter] = useState<Filter>("all");
  const [speed, setSpeed] = useState(initial.settings.speed);
  const [pause, setPause] = useState(initial.settings.pause_ms);
  const [lexicon, setLexicon] = useState(initial.settings.lexicon);
  const [questionText, setQuestionText] = useState(initial.question.text || initial.question.script);
  const [referenceText, setReferenceText] = useState(initialReference?.text || initialReference?.script || "");
  const [recording, setRecording] = useState<string | null>(null);
  const [audioError, setAudioError] = useState("");
  const recorder = useRef<Recorder | null>(null);
  const playing = useRef<HTMLAudioElement | null>(null);
  const { pending, error, message, run } = useAction();

  const flagged = data.items.filter((item) => item.flags.length && !item.recorded);
  const top = useMemo(() => new Set(data.items.filter((item) => item.plays > 0).sort((a, b) => b.plays - a.plays).slice(0, 10).map((item) => item.hash)), [data.items]);
  const shown = filter === "flag" ? flagged : filter === "top"
    ? data.items.filter((item) => top.has(item.hash)).sort((a, b) => b.plays - a.plays) : data.items;
  const recorded = data.items.filter((item) => item.recorded).length;

  async function refresh() {
    const next = await apiSend<VoiceData>("/api/voice", "GET");
    setData(next);
    setQuestionText(next.question.text || next.question.script);
  }

  async function refreshReference() {
    if (!reference) return;
    const next = await apiSend<ReferenceVoice>("/api/voice/reference", "GET");
    setReference(next); setReferenceText(next.text || next.script);
  }

  useEffect(() => {
    if (!reference?.preview.running) return;
    const timer = window.setInterval(() => void refreshReference(), 3000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reference?.preview.running]);

  function play(url: string, phone = false) {
    setAudioError(""); playing.current?.pause();
    const audio = new Audio(`${url}?${phone ? "phone=1&" : ""}t=${Date.now()}`);
    playing.current = audio;
    void audio.play().catch(() => setAudioError("Аудио алга. Эхлээд “Аудио бэлдэх” дарна уу."));
  }

  function saveSettings() {
    const changed = speed !== data.settings.speed || pause !== data.settings.pause_ms;
    if (changed && !window.confirm("Хурд эсвэл завсар өөрчлөгдвөл бүх аудио дахин үүснэ. Хадгалах уу?")) return;
    void run(async () => {
      await apiSend("/api/voice/settings", "PUT", { speed, pause_ms: pause,
        lexicon: lexicon.filter((row) => row.word.trim() && row.say.trim()) });
      await refresh();
    }, "Хадгаллаа. Аудио бэлдэх дарна уу ✓");
  }

  function regenerate(item: VoiceItem) {
    if (!window.confirm("Энэ өгүүлбэрийг өөр хувилбараар дахин үүсгэх үү?")) return;
    void run(async () => { await apiSend(`/api/voice/regenerate/${item.hash}`, "POST"); await refresh(); }, "Дахин үүсгэх ажил эхэллээ");
  }

  function deleteRecording(item: VoiceItem) {
    if (!window.confirm("Энэ бичлэгийг устгаад TTS аудио руу буцах уу?")) return;
    void run(async () => { await apiSend(`/api/voice/recording/${item.hash}`, "DELETE"); await refresh(); }, "Бичлэг устлаа");
  }

  async function toggleRecord(hash: string) {
    if (recorder.current) return stopRecord();
    setAudioError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: false } });
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const node = ctx.createScriptProcessor(4096, 1, 1);
      const chunks: Float32Array[] = [];
      node.onaudioprocess = (event) => chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      source.connect(node); node.connect(ctx.destination);
      recorder.current = { ctx, stream, node, chunks, hash };
      setRecording(hash);
    } catch (err) {
      setAudioError(`Микрофон ашиглах зөвшөөрөл хэрэгтэй: ${(err as Error).message}`);
    }
  }

  async function stopRecord() {
    const current = recorder.current;
    if (!current) return;
    recorder.current = null; setRecording(null);
    current.node.disconnect(); current.stream.getTracks().forEach((track) => track.stop());
    const rate = current.ctx.sampleRate; await current.ctx.close();
    const form = new FormData(); form.append("file", encodeWav(current.chunks, rate), "recording.wav");
    if (current.hash === "__question__") form.append("text", questionText);
    if (current.hash === "__reference__") form.append("text", referenceText);
    const path = current.hash === "__question__" ? "/api/voice/question"
      : current.hash === "__reference__" ? "/api/voice/reference" : `/api/voice/recording/${current.hash}`;
    void run(async () => {
      await apiSend(path, "POST", form);
      if (current.hash === "__reference__") await refreshReference(); else await refresh();
    }, "Бичлэг хадгалагдлаа ✓");
  }

  function uploadSpecial(event: ChangeEvent<HTMLInputElement>, kind: "question" | "reference") {
    const file = event.target.files?.[0]; if (!file) return;
    const form = new FormData(); form.append("file", file);
    form.append("text", kind === "question" ? questionText : referenceText);
    void run(async () => {
      await apiSend(kind === "question" ? "/api/voice/question" : "/api/voice/reference", "POST", form);
      if (kind === "question") await refresh(); else await refreshReference();
    }, "Бичлэг хадгалагдлаа ✓");
    event.target.value = "";
  }

  return (
    <div className="space-y-7">
      <section className="border-b border-line pb-8">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">Чанарын шалгалт</h2>
          <span className="text-sm text-muted">{data.qa_at ? `Сүүлд шалгасан ${formatDateTime(data.qa_at)}` : "Аудио бэлдэхэд автоматаар шалгана"}</span></div>
        <p className="mt-5 max-w-5xl leading-7 text-muted">Клип бүрийг яриа танихаар буцааж уншуулж буруу дуудлага, хэт хурдан эсвэл удаан, чимээгүй, тасарсан дууг илрүүлнэ. Тэмдэглэгдсэн клипийг сонсоод ↻ дарж дахин үүсгэх, эсвэл ● өөрөө бичнэ.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>Бүгд ({data.items.length})</FilterButton>
          <FilterButton active={filter === "flag"} onClick={() => setFilter("flag")}>⚠ Шалгах ({flagged.length})</FilterButton>
          <FilterButton active={filter === "top"} onClick={() => setFilter("top")}>Их тоглогддог ({top.size})</FilterButton>
        </div>
      </section>

      <section className="overflow-hidden rounded-[14px] bg-panel px-[22px]">
        {shown.length ? <div className="divide-y divide-line">{shown.map((item) => (
          <div key={item.hash} className="flex items-center gap-4 py-4">
            <div className="flex shrink-0 gap-2">
              <IconButton label="Сонсох" onClick={() => play(`/api/voice/audio/${item.hash}`)}>▶</IconButton>
              <IconButton label="Утасны чанар" onClick={() => play(`/api/voice/audio/${item.hash}`, true)}>☎</IconButton>
              <IconButton label="Өөрөө бичих" danger active={recording === item.hash} onClick={() => void toggleRecord(item.hash)}>{recording === item.hash ? "■" : "●"}</IconButton>
            </div>
            <div className="min-w-0 flex-1"><p className="leading-6">{item.text}</p><div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span>{item.kind}{item.plays ? ` · ${item.plays} удаа тоглогдсон` : ""}</span>
              {top.has(item.hash) && <Tag>Их тоглогддог</Tag>}
              {!item.recorded && item.flags.map((flag) => <Tag key={flag} tone="warn">⚠ {flag}</Tag>)}
            </div></div>
            <div className="flex shrink-0 items-center gap-2">{item.recorded
              ? <><Tag>Бичлэг</Tag><IconButton label="Бичлэг устгах" danger onClick={() => deleteRecording(item)}>×</IconButton></>
              : <><Tag tone="gray">TTS{item.seed ? ` #${item.seed + 1}` : ""}</Tag><IconButton label="Дахин үүсгэх" onClick={() => regenerate(item)}>↻</IconButton></>}</div>
          </div>
        ))}</div> : <p className="py-10 text-center text-muted">Алга ✓</p>}
      </section>

      <section className="border-b border-line pb-8">
        <p className="font-semibold">Өгүүлбэр бүрийг бичих (хамгийн байгалийн)</p>
        <div className="mt-3 font-mono text-5xl font-bold">{recorded}<span className="text-2xl font-normal text-muted">/ {data.items.length} өгүүлбэр</span></div>
        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full bg-brand" style={{ width: `${data.items.length ? recorded / data.items.length * 100 : 0}%` }} /></div>
        <p className="mt-4 rounded-[10px] bg-panel px-4 py-3 text-sm text-muted"><b className="text-fg">{data.items.length - recorded}</b> өгүүлбэр TTS хоолойгоор тоглогдож байна.</p>
      </section>

      <section className="border-b border-line pb-8">
        <h2 className="font-semibold">Дуудлага</h2>
        <p className="mt-3 leading-7 text-muted">TTS буруу дууддаг үг, товчлолыг хэрхэн дуудахыг заана. Хурд, завсар өөрчилбөл бүх аудио дахин үүснэ.</p>
        <div className="mt-5 rounded-[14px] bg-panel px-[22px] py-5">
          <Range label="Хурд" value={speed} min={0.7} max={1.15} step={0.05} suffix="" onChange={setSpeed} />
          <Range label="Өгүүлбэр хоорондын завсар" value={pause} min={100} max={1000} step={50} suffix="мс" onChange={setPause} />
          <p className="mt-5 text-sm text-muted">Дуудлагын толь (бичигдсэн → дуудах)</p>
          <div className="mt-2 space-y-2">{lexicon.map((row, index) => <div className="flex gap-2" key={index}>
            <input className="w-44 rounded-[10px] border border-line-2 bg-bg px-3 py-2" placeholder="CV" value={row.word}
              onChange={(event) => setLexicon((all) => all.map((item, i) => i === index ? { ...item, word: event.target.value } : item))} />
            <span className="self-center text-muted">→</span><input className="min-w-0 flex-1 rounded-[10px] border border-line-2 bg-bg px-3 py-2" placeholder="си ви" value={row.say}
              onChange={(event) => setLexicon((all) => all.map((item, i) => i === index ? { ...item, say: event.target.value } : item))} />
            <IconButton label="Устгах" danger onClick={() => setLexicon((all) => all.filter((_, i) => i !== index))}>×</IconButton>
          </div>)}</div>
          <div className="mt-4 flex gap-3"><Button onClick={() => setLexicon((all) => [...all, { word: "", say: "" }])}>+ Үг нэмэх</Button><Button variant="primary" onClick={saveSettings} disabled={pending}>Хадгалах</Button></div>
        </div>
      </section>

      <section className="border-b border-line pb-8"><div className="flex items-center gap-3"><h2 className="font-semibold">Асуултын аялга</h2><Tag tone={data.question.exists ? "ok" : "gray"}>{data.question.exists ? "Идэвхтэй" : "Алга"}</Tag></div>
        <p className="mt-3 leading-7 text-muted">“...байна уу?” гэх мэт асуултыг өсөх өнгөөр уншуулахын тулд 2–8 секундын бичлэг оруулна. Зөвхөн өөрийн, эсвэл зөвшөөрөл өгсөн хүний хоолой ашиглана.</p>
        <div className="mt-5 rounded-[14px] bg-panel px-[22px] py-5"><label className="text-sm text-muted">Унших асуулт<input className="mt-2 w-full rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-fg" value={questionText} onChange={(event) => setQuestionText(event.target.value)} /></label>
          <div className="mt-4 flex flex-wrap gap-3"><Button onClick={() => void toggleRecord("__question__")}>{recording === "__question__" ? "■ Зогсоох" : "● Бичих"}</Button>
            <UploadButton onChange={(event) => uploadSpecial(event, "question")} />
            {data.question.exists && <><Button onClick={() => play("/api/voice/question/audio")}>▶ Сонсох</Button><Button className="text-danger" onClick={() => void run(async () => { await apiSend("/api/voice/question", "DELETE"); await refresh(); }, "Асуултын бичлэг устлаа")}>Устгах</Button></>}</div>
        </div>
      </section>

      {reference && <section className="border-b border-line pb-8"><div className="flex items-center gap-3"><h2 className="font-semibold">Лавлах хоолой (voice clone · бүх байгууллага)</h2><Tag tone={reference.exists ? "ok" : "gray"}>{reference.exists ? `Идэвхтэй · ${reference.seconds}с` : "Анхдагч хоолой"}</Tag></div>
        <p className="mt-3 leading-7 text-muted">Монгол хүний 5–15 секундын жинхэнэ яриаг сонсоод AI тэр хоолой, хэмнэлийг дуурайна. Зөвхөн өөрийн, эсвэл зөвшөөрөл өгсөн хүний хоолой ашиглана.</p>
        <div className="mt-5 rounded-[14px] bg-panel px-[22px] py-5"><label className="text-sm text-muted">Унших бичвэр<textarea className="mt-2 min-h-20 w-full rounded-[10px] border border-line-2 bg-bg p-3 text-fg" value={referenceText} onChange={(event) => setReferenceText(event.target.value)} /></label>
          <div className="mt-4 flex flex-wrap gap-3"><Button onClick={() => void toggleRecord("__reference__")}>{recording === "__reference__" ? "■ Зогсоох" : "● Бичих"}</Button><UploadButton onChange={(event) => uploadSpecial(event, "reference")} />
            {reference.exists && <><Button onClick={() => play("/api/voice/reference/audio")}>▶ Лавлах хоолой</Button><Button className="text-danger" onClick={() => void run(async () => { await apiSend("/api/voice/reference", "DELETE"); await refreshReference(); }, "Анхдагч хоолой руу буцлаа")}>Анхдагч руу буцах</Button></>}
            <Button className="ml-auto" disabled={reference.preview.running || !reference.exists} onClick={() => void run(async () => { await apiSend("/api/voice/reference/preview", "POST"); await refreshReference(); }, "Жишээ үүсгэж байна…")}>{reference.preview.running ? "Үүсгэж байна…" : "Туршиж сонсох"}</Button></div>
          {reference.preview.files.length > 0 && <div className="mt-4 flex gap-2"><span className="text-sm text-muted">Жишээ:</span>{reference.preview.files.map((name, index) => <Button key={name} onClick={() => play(`/api/voice/reference/preview/${name}`)}>▶ {index + 1}</Button>)}</div>}
        </div>
      </section>}

      <BuildPanel />
      <ActionStatus error={error || audioError} message={message} />
    </div>
  );
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return <Button variant={active ? "primary" : "ghost"} onClick={onClick}>{children}</Button>;
}

function IconButton({ label, danger = false, active = false, onClick, children }: { label: string; danger?: boolean; active?: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" title={label} aria-label={label} onClick={onClick}
    className={`grid size-10 cursor-pointer place-items-center rounded-[10px] border font-semibold ${danger ? "border-danger/50 text-danger" : "border-line-2"} ${active ? "bg-danger/15" : "bg-transparent hover:border-brand"}`}>{children}</button>;
}

function Range({ label, value, min, max, step, suffix, onChange }: { label: string; value: number; min: number; max: number; step: number; suffix: string; onChange: (value: number) => void }) {
  return <label className="mb-4 grid items-center gap-3 text-sm text-muted sm:grid-cols-[190px_1fr_70px]"><span>{label}</span><input className="accent-brand" type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /><span className="font-mono text-fg">{value}{suffix}</span></label>;
}

function UploadButton({ onChange }: { onChange: (event: ChangeEvent<HTMLInputElement>) => void }) {
  return <label className="inline-flex cursor-pointer items-center rounded-[10px] border-[1.5px] border-line-2 px-4 py-[9px] text-sm font-semibold hover:border-brand">↑ WAV оруулах<input type="file" accept="audio/wav,.wav" className="hidden" onChange={onChange} /></label>;
}

function encodeWav(chunks: Float32Array[], sampleRate: number) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + length * 2); const view = new DataView(buffer);
  const text = (offset: number, value: string) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  text(0, "RIFF"); view.setUint32(4, 36 + length * 2, true); text(8, "WAVE"); text(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, "data"); view.setUint32(40, length * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const sample of chunk) { view.setInt16(offset, Math.max(-1, Math.min(1, sample)) * 0x7fff, true); offset += 2; }
  return new Blob([buffer], { type: "audio/wav" });
}
