"use client";

import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { apiSend } from "@/lib/client";
import type { BuildStatus, KnowledgeFile, KnowledgeResponse } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const button = "rounded-[10px] border-[1.5px] border-line-2 px-5 py-3 text-sm font-semibold transition hover:border-brand disabled:cursor-default disabled:opacity-45";

export function KnowledgeManager({ initial }: { initial: KnowledgeResponse }) {
  const first = initial.files.find((file) => file.editable)?.name ?? null;
  const [data, setData] = useState(initial);
  const [active, setActive] = useState<string | null>(first);
  const [content, setContent] = useState("");
  const [docLoading, setDocLoading] = useState(Boolean(first));
  const [build, setBuild] = useState<BuildStatus>({ state: "idle", running: false, ahead: 0, code: null, finished: null, log: [] });
  const { pending, error, message, run } = useAction();
  const audio = useRef<HTMLAudioElement | null>(null);

  const loadDocument = useCallback(async (name: string) => {
    setDocLoading(true);
    try {
      const doc = await apiSend<{ content: string }>(`/api/knowledge/file/${encodeURIComponent(name)}`, "GET");
      setContent(doc.content);
    } finally { setDocLoading(false); }
  }, []);

  const refresh = useCallback(async () => {
    const next = await apiSend<KnowledgeResponse>("/api/knowledge", "GET");
    setData(next);
    return next;
  }, []);

  const pollBuild = useCallback(async () => {
    const status = await apiSend<BuildStatus>("/api/knowledge/build", "GET");
    setBuild(status);
    if (!status.running && status.finished) await refresh();
    return status;
  }, [refresh]);

  useEffect(() => {
    queueMicrotask(() => { if (first) void loadDocument(first); void pollBuild(); });
  }, [first, loadDocument, pollBuild]);
  useEffect(() => {
    if (!build.running) return;
    const timer = window.setInterval(() => void pollBuild(), 2000);
    return () => window.clearInterval(timer);
  }, [build.running, pollBuild]);

  function select(file: KnowledgeFile) {
    setActive(file.name);
    if (file.editable) void run(() => loadDocument(file.name), "");
    else { setContent(""); setDocLoading(false); }
  }

  function newDocument() {
    let name = window.prompt("Файлын нэр (жишээ нь: une.md)")?.trim();
    if (!name) return;
    if (!/\.(md|txt)$/i.test(name)) name += ".md";
    run(async () => {
      await apiSend(`/api/knowledge/file/${encodeURIComponent(name!)}`, "PUT", { content: "# Гарчиг (уншигдахгүй)\n\n" });
      await refresh(); setActive(name!); await loadDocument(name!);
    }, `${name} үүслээ`);
  }

  function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData(); form.append("file", file);
    run(async () => { await apiSend("/api/knowledge/upload", "POST", form); await refresh(); setActive(file.name); if (/\.(md|txt)$/i.test(file.name)) await loadDocument(file.name); }, `${file.name} орууллаа`);
    event.target.value = "";
  }

  function save() {
    if (active) run(() => apiSend(`/api/knowledge/file/${encodeURIComponent(active)}`, "PUT", { content }), "Хадгаллаа. Аудио бэлдэхэд бэлэн.");
  }

  function remove() {
    if (!active || !window.confirm(`${active}-г устгах уу?`)) return;
    run(async () => { await apiSend(`/api/knowledge/file/${encodeURIComponent(active)}`, "DELETE"); const next = await refresh(); const name = next.files.find((f) => f.editable)?.name ?? null; setActive(name); if (name) await loadDocument(name); else setContent(""); }, "Устгалаа");
  }

  function startBuild() {
    run(async () => { const status = await apiSend<BuildStatus>("/api/knowledge/build", "POST"); setBuild(status); }, "Аудио бэлдэж эхэллээ");
  }

  function play(hash: string) {
    audio.current?.pause(); audio.current = new Audio(`/api/knowledge/audio/${hash}`); void audio.current.play();
  }

  const activeFile = data.files.find((file) => file.name === active);
  const log = build.state === "queued" ? `Дараалалд байна (өмнө нь ${build.ahead} ажил)...` : build.log.join("\n") || "—";
  return <div className="space-y-7">
    <section className="rounded-[18px] bg-panel p-7 max-md:p-4">
      <div className="mb-5 flex flex-wrap gap-2.5">
        {data.files.map((file) => <button key={file.name} onClick={() => select(file)} className={`${button} font-mono ${file.name === active ? "border-brand text-brand" : "text-fg"}`}>{file.name}</button>)}
        <button className={button} onClick={newDocument}>+ Шинэ файл</button>
        <label className={`${button} cursor-pointer border-dashed text-muted`}><input className="hidden" type="file" accept=".md,.txt,.pdf,.docx" onChange={upload} />↑ Файл оруулах</label>
      </div>
      {active ? <>
        <textarea aria-label={`${active} агуулга`} disabled={!activeFile?.editable || docLoading} value={content} onChange={(e) => setContent(e.target.value)} placeholder={activeFile?.editable ? "" : "PDF/DOCX файлыг энд засах боломжгүй. Шинээр оруулна уу."} className="min-h-[430px] w-full resize-y rounded-[12px] border-[1.5px] border-line-2 bg-bg p-4 font-mono text-sm leading-6 text-fg outline-none focus:border-brand disabled:text-muted" />
        <div className="mt-3 flex flex-wrap items-center gap-3"><button className={`${button} border-brand bg-brand text-bg hover:bg-brand-2`} onClick={save} disabled={pending || !activeFile?.editable}>Хадгалах</button><button className={`${button} text-danger hover:border-danger`} onClick={remove} disabled={pending}>Устгах</button><span className="text-sm text-muted">{active}</span></div>
      </> : <div className="py-16 text-center text-muted">Файл алга. “+ Шинэ файл” дарна уу.</div>}
    </section>

    <section className="rounded-[18px] bg-panel p-7 max-md:p-4">
      <div className="flex flex-wrap items-center gap-4"><h2 className="flex-1 text-base font-semibold">Аудио бэлдэх</h2><button className={`${button} border-brand bg-brand text-bg hover:bg-brand-2`} onClick={startBuild} disabled={build.running}>{build.state === "queued" ? "Дараалалд..." : build.running ? "Бэлдэж байна..." : "Аудио бэлдэх"}</button></div>
      <p className="mt-5 text-sm leading-6 text-muted">Мэдээллээс асуулт, тодруулах сэдэв, FAQ-г автоматаар үүсгэж, шинэ/өөрчлөгдсөн өгүүлбэрийг аудио болгоод (өгүүлбэр бүр ~5с) AI-г сургана. Өөрийн бичлэгтэйг TTS хийхгүй. Олон байгууллага зэрэг бэлдвэл дараалалд орно. <b className="text-fg">Бэлдэх хугацаанд AI сервер түр зогсоно</b> (8GB санах ой) — дуудлагагүй үед ажиллуулна уу.</p>
      <pre className="mt-5 max-h-72 min-h-20 overflow-auto whitespace-pre-wrap rounded-[12px] bg-bg p-4 font-mono text-xs leading-5 text-muted">{log}</pre>
    </section>

    <section className="rounded-[18px] bg-panel p-7 max-md:p-4">
      <h2 className="mb-4 font-semibold">Аудиотой өгүүлбэрүүд ({data.facts.length}) <span className="font-normal text-muted">· {data.indexed_at || "бэлдээгүй"}</span></h2>
      <div className="divide-y divide-line">{data.facts.map((fact) => <div key={`${fact.hash}-${fact.text}`} className="flex items-center gap-4 py-3"><button className="grid size-10 shrink-0 place-items-center rounded-[10px] border border-line-2 hover:border-brand disabled:opacity-35" onClick={() => play(fact.hash)} disabled={!fact.has_audio}>▶</button><div className="min-w-0 flex-1">{fact.text}<div className="text-xs text-muted">{fact.source}</div></div><span className={`rounded-md px-2 py-1 text-xs ${fact.recorded ? "bg-brand/10 text-brand" : "bg-line text-muted"}`}>{fact.recorded ? "Бичлэг" : "TTS"}</span></div>)}{!data.facts.length && <p className="py-8 text-center text-muted">Аудио бэлдээгүй байна.</p>}</div>
    </section>
    <div className="min-h-5"><ActionStatus error={error} message={message} /></div>
  </div>;
}
