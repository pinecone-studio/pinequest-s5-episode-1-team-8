"use client";

import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { apiSend } from "@/lib/client";
import type { BuildStatus, KnowledgeFile, KnowledgeResponse } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const button = "rounded-[10px] border-[1.5px] border-line-2 px-5 py-3 text-sm font-semibold transition hover:border-brand disabled:cursor-default disabled:opacity-45";

export function KnowledgeManager({ initial, isAdmin }: { initial: KnowledgeResponse; isAdmin: boolean }) {
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
    let name = window.prompt("Шинэ текстийн нэр (жишээ нь: une.md)")?.trim();
    if (!name) return;
    if (!/\.(md|txt)$/i.test(name)) name += ".md";
    run(async () => {
      await apiSend(`/api/knowledge/file/${encodeURIComponent(name!)}`, "PUT", { content: "# Гарчиг (уншигдахгүй)\n\n" });
      await refresh(); setActive(name!); await loadDocument(name!); markBuildNeeded();
    }, `${name} үүслээ`);
  }

  function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData(); form.append("file", file);
    run(async () => { await apiSend("/api/knowledge/upload", "POST", form); await refresh(); setActive(file.name); if (/\.(md|txt)$/i.test(file.name)) await loadDocument(file.name); markBuildNeeded(); }, `${file.name} орууллаа`);
    event.target.value = "";
  }

  function save() {
    if (active) run(async () => { await apiSend(`/api/knowledge/file/${encodeURIComponent(active)}`, "PUT", { content }); markBuildNeeded(); }, "Хадгаллаа. Мэдээллээ бэлдэнэ үү.");
  }

  function remove() {
    if (!active || !window.confirm(`${active}-г устгах уу?`)) return;
    run(async () => { await apiSend(`/api/knowledge/file/${encodeURIComponent(active)}`, "DELETE"); const next = await refresh(); const name = next.files.find((f) => f.editable)?.name ?? null; setActive(name); if (name) await loadDocument(name); else setContent(""); markBuildNeeded(); }, "Устгалаа");
  }

  function markBuildNeeded() {
    setBuild({ state: "idle", running: false, ahead: 0, code: null, finished: null, log: [] });
  }

  function startBuild() {
    run(async () => { const status = await apiSend<BuildStatus>("/api/knowledge/build", "POST"); setBuild(status); },
      isAdmin ? "Аудио бэлдэж эхэллээ" : "Мэдээллийг бэлдэж эхэллээ");
  }

  function cancelBuild() {
    if (!window.confirm("Бэлдэж буй ажлыг зогсоох уу? Өмнө бэлдсэн аудио хэвээр ажиллана, дараа нь дахин бэлдэж болно.")) return;
    run(async () => { setBuild(await apiSend<BuildStatus>("/api/knowledge/build/cancel", "POST")); }, "Зогсоолоо — өмнө бэлдсэн аудио хэвээр ажиллана");
  }

  function play(hash: string) {
    audio.current?.pause(); audio.current = new Audio(`/api/knowledge/audio/${hash}`); void audio.current.play();
  }

  const activeFile = data.files.find((file) => file.name === active);
  const log = build.state === "queued" ? `Дараалалд байна (өмнө нь ${build.ahead} ажил)...` : build.log.join("\n") || "—";
  const progressLine = [...build.log].reverse().find((line) => /\[\d+\/\d+\]/.test(line));
  const progress = progressLine?.match(/\[(\d+)\/(\d+)\]/);
  const remaining = progressLine?.match(/~\d+ мин үлдсэн/)?.[0];
  const progressLabel = progress ? `${progress[1]} / ${progress[2]}${remaining ? ` · ${remaining}` : ""}` : null;
  const buildButton = build.state === "queued" ? "Дараалалд..."
    : build.running ? progressLabel ?? "Бэлдэж байна..."
    : build.state === "done" ? "Мэдээлэл бэлэн ✓"
    : build.state === "error" ? "Дахин оролдох"
    : isAdmin ? "Аудио бэлдэх" : "Мэдээллийг бэлдэх";
  return <div className="space-y-7">
    <section className="rounded-[18px] bg-panel p-7 max-md:p-4">
      <div className="mb-5 rounded-[12px] border border-line-2 bg-bg p-4">
        <h2 className="mb-1 font-semibold">Мэдээлэл нэмэх</h2>
        <p className="mb-3 text-sm text-muted">PDF, Word, Markdown эсвэл TXT файл оруулах, эсвэл шинэ текст бичиж болно.</p>
        <div className="flex flex-wrap gap-2.5">
          <label className={`${button} cursor-pointer border-brand bg-brand text-bg hover:bg-brand-2`}>
            <input className="hidden" type="file" accept=".md,.txt,.pdf,.docx" onChange={upload} />
            ↑ Компьютероос файл оруулах
          </label>
          <button className={button} onClick={newDocument}>+ Шинэ текст бичих</button>
        </div>
        <div className="mt-3 min-h-5"><ActionStatus error={error} message={message} /></div>
      </div>
      <div className="mb-5 flex flex-wrap gap-2.5">
        {data.files.map((file) => <button key={file.name} onClick={() => select(file)} className={`${button} font-mono ${file.name === active ? "border-brand text-brand" : "text-fg"}`}>{file.name}</button>)}
      </div>
      {activeFile ? activeFile.editable ? <>
        <textarea aria-label={`${active} агуулга`} disabled={docLoading} value={content} onChange={(e) => setContent(e.target.value)} className="min-h-[430px] w-full resize-y rounded-[12px] border-[1.5px] border-line-2 bg-bg p-4 font-mono text-sm leading-6 text-fg outline-none focus:border-brand disabled:text-muted" />
        <div className="mt-3 flex flex-wrap items-center gap-3"><button className={`${button} border-brand bg-brand text-bg hover:bg-brand-2`} onClick={save} disabled={pending}>Хадгалах</button><button className={`${button} text-danger hover:border-danger`} onClick={remove} disabled={pending}>Устгах</button><span className="text-sm text-muted">{active}</span></div>
      </> : (
        <div className="rounded-[12px] border border-brand/40 bg-brand/5 p-5">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="text-brand" aria-hidden>✓</span>
            <h2 className="font-semibold">Файл хадгалагдсан</h2>
          </div>
          <p className="break-all font-mono text-sm">{activeFile.name}</p>
          <p className="mt-2 text-sm text-muted">
            {formatFileSize(activeFile.size)} · PDF болон Word файлыг web дээр засахгүй, харин AI агуулгыг нь уншиж ашиглана.
          </p>
          <button className={`${button} mt-4 text-danger hover:border-danger`} onClick={remove} disabled={pending}>Устгах</button>
        </div>
      ) : <div className="py-16 text-center text-muted">Мэдээлэл алга. Компьютероос файл оруулах эсвэл шинэ текст бичнэ үү.</div>}
      {!isAdmin && (
        <div className="mt-6 flex justify-end">
          <button
            className={`${button} border-brand bg-brand text-bg hover:bg-brand-2`}
            onClick={startBuild}
            disabled={!data.files.length || build.running || build.state === "done"}
          >
            {!data.files.length ? "Эхлээд мэдээлэл оруулна уу" : buildButton}
          </button>
        </div>
      )}
    </section>

    {isAdmin && <section className="rounded-[18px] bg-panel p-7 max-md:p-4">
      <div className="flex flex-wrap items-center gap-4"><h2 className="flex-1 text-base font-semibold">{isAdmin ? "Өөрчлөлтийг ашиглах" : "Дуудлагад ашиглах"}</h2><button className={`${button} border-brand bg-brand text-bg hover:bg-brand-2`} onClick={startBuild} disabled={build.running}>{buildButton}</button>{build.running && <button className={`${button} hover:border-danger hover:text-danger`} onClick={cancelBuild} disabled={pending}>⏹ Зогсоох</button>}</div>
      <p className="mt-5 text-sm leading-6 text-muted">
        {isAdmin
          ? <>Мэдээллээс асуулт, тодруулах сэдэв, FAQ-г автоматаар үүсгэж, шинэ/өөрчлөгдсөн өгүүлбэрийг аудио болгоно. <b className="text-fg">Бэлдэх хугацаанд AI сервер түр зогсоно.</b></>
          : "PDF эсвэл текстээ оруулсны дараа энэ товчийг дарна. Бэлдэж дуусмагц AI туслах залгагчийн асуултад шинэ мэдээллээр хариулна."}
      </p>
      {build.state === "done" && (
        <p role="status" className="mt-4 rounded-[10px] bg-brand/10 px-3 py-2.5 text-sm text-brand">
          ✓ Мэдээлэл бэлэн боллоо. AI туслах шинэ мэдээллээр хариулна.
        </p>
      )}
      {build.state === "error" && (
        <p role="alert" className="mt-4 rounded-[10px] bg-danger/10 px-3 py-2.5 text-sm text-danger">
          Мэдээллийг бүрэн бэлдэж чадсангүй. Дахин бэлдэх товчийг дарна уу.
        </p>
      )}
      {build.state === "canceled" && (
        <p role="status" className="mt-4 rounded-[10px] bg-warn/10 px-3 py-2.5 text-sm text-warn">
          Бэлдэх үйлдлийг зогсоосон. Шинэ мэдээлэл хараахан ашиглагдахгүй.
        </p>
      )}
      <pre className="mt-5 max-h-72 min-h-20 overflow-auto whitespace-pre-wrap rounded-[12px] bg-bg p-4 font-mono text-xs leading-5 text-muted">{log}</pre>
    </section>}

    {isAdmin && <section className="rounded-[18px] bg-panel p-7 max-md:p-4">
      <h2 className="mb-4 font-semibold">Аудиотой өгүүлбэрүүд ({data.facts.length}) <span className="font-normal text-muted">· {data.indexed_at || "бэлдээгүй"}</span></h2>
      <div className="divide-y divide-line">{data.facts.map((fact) => <div key={`${fact.hash}-${fact.text}`} className="flex items-center gap-4 py-3"><button className="grid size-10 shrink-0 place-items-center rounded-[10px] border border-line-2 hover:border-brand disabled:opacity-35" onClick={() => play(fact.hash)} disabled={!fact.has_audio}>▶</button><div className="min-w-0 flex-1">{fact.text}<div className="text-xs text-muted">{fact.source}</div></div><span className={`rounded-md px-2 py-1 text-xs ${fact.recorded ? "bg-brand/10 text-brand" : "bg-line text-muted"}`}>{fact.recorded ? "Бичлэг" : "TTS"}</span></div>)}{!data.facts.length && <p className="py-8 text-center text-muted">Аудио бэлдээгүй байна.</p>}</div>
    </section>}
  </div>;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
