"use client";

import { useState, type ChangeEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { KnowledgeFile, KnowledgeResponse } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function KnowledgeManager({ initial }: { initial: KnowledgeResponse }) {
  const [files, setFiles] = useState(initial.files);
  const [active, setActive] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const { pending, error, message, run } = useAction();

  async function refresh(select?: string) {
    const data = await apiSend<KnowledgeResponse>("/api/knowledge", "GET");
    setFiles(data.files);
    if (select) await open(data.files.find((f) => f.name === select));
  }

  async function open(file?: KnowledgeFile) {
    if (!file?.editable) return;
    const doc = await apiSend<{ name: string; content: string }>(`/api/knowledge/file/${encodeURIComponent(file.name)}`, "GET");
    setActive(doc.name);
    setContent(doc.content);
  }

  function createFile() {
    const name = window.prompt("Шинэ файлын нэр (.md эсвэл .txt)", "medeelel.md")?.trim();
    if (!name) return;
    run(async () => {
      await apiSend(`/api/knowledge/file/${encodeURIComponent(name)}`, "PUT", { content: "" });
      await refresh(name);
    }, "Шинэ файл үүслээ");
  }

  function save() {
    if (!active) return;
    run(() => apiSend(`/api/knowledge/file/${encodeURIComponent(active)}`, "PUT", { content }), "Хадгаллаа ✓");
  }

  function remove(name: string) {
    if (!window.confirm(`${name} файлыг устгах уу?`)) return;
    run(async () => {
      await apiSend(`/api/knowledge/file/${encodeURIComponent(name)}`, "DELETE");
      if (active === name) { setActive(null); setContent(""); }
      await refresh();
    }, "Устгалаа");
  }

  function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    run(async () => { await apiSend("/api/knowledge/upload", "POST", form); await refresh(file.name); }, "Файл орлоо ✓");
    e.target.value = "";
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
      <div className="rounded-xl border border-line bg-panel-2 p-3">
        <div className="mb-3 flex gap-2">
          <Button type="button" onClick={createFile} disabled={pending}>+ Файл</Button>
          <label className="cursor-pointer rounded-[10px] border-[1.5px] border-line-2 px-4 py-[9px] text-sm font-semibold hover:border-brand">
            ↑ Оруулах<input className="hidden" type="file" accept=".md,.txt,.pdf,.docx" onChange={upload} />
          </label>
        </div>
        <div className="space-y-1">
          {files.map((file) => (
            <div key={file.name} className={`flex items-center gap-2 rounded-lg px-3 py-2 ${active === file.name ? "bg-brand/10 text-brand" : "hover:bg-line"}`}>
              <button className="min-w-0 flex-1 truncate text-left text-sm" onClick={() => run(() => open(file))}>{file.name}</button>
              <span className="font-mono text-[11px] text-muted">{Math.ceil(file.size / 1024)}KB</span>
              <button className="text-danger" aria-label={`${file.name} устгах`} onClick={() => remove(file.name)}>×</button>
            </div>
          ))}
          {!files.length && <p className="p-3 text-sm text-muted">Мэдээллийн файл алга.</p>}
        </div>
      </div>
      <div>
        {active ? (
          <>
            <div className="mb-3 flex items-center justify-between"><b>{active}</b><Button variant="primary" onClick={save} disabled={pending}>Хадгалах</Button></div>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} className="min-h-[430px] w-full rounded-xl border border-line-2 bg-panel p-4 font-mono text-sm leading-7 outline-none focus:border-brand" />
          </>
        ) : <div className="grid min-h-[430px] place-items-center rounded-xl border border-dashed border-line-2 text-muted">Засах .md эсвэл .txt файлаа сонгоно уу</div>}
        <div className="mt-3 min-h-5"><ActionStatus error={error} message={message} /></div>
      </div>
    </div>
  );
}
