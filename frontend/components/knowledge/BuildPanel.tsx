"use client";

import { useCallback, useEffect, useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { JobStatus } from "@/lib/types";

export function BuildPanel({
  startPath = "/api/knowledge/build",
  statusPath = "/api/knowledge/build",
  title = "Аудио бэлдэх",
  description = "Мэдээллээс асуулт, тодруулах сэдэв, FAQ-г автоматаар үүсгэж, шинэ эсвэл өөрчлөгдсөн өгүүлбэрийг аудио болгоод AI-г сургана. Өөрийн бичлэгтэй өгүүлбэрт TTS ажиллахгүй. Бэлдэх хугацаанд AI сервер түр зогсож болох тул дуудлагагүй үед ажиллуулна уу.",
  buttonLabel = "Аудио бэлдэх",
}: {
  startPath?: string;
  statusPath?: string;
  title?: string;
  description?: string;
  buttonLabel?: string;
}) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    try {
      const next = await apiSend<JobStatus>(statusPath, "GET");
      setStatus(next);
      if (!next.running && next.code === 0 && next.finished) setMessage("Бэлэн боллоо ✓");
    } catch (err) {
      setError((err as Error).message);
    }
  }, [statusPath]);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  useEffect(() => {
    if (!status?.running) return;
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(timer);
  }, [refresh, status?.running]);

  async function start() {
    setError(""); setMessage("");
    try {
      const next = await apiSend<JobStatus>(startPath, "POST");
      setStatus(next);
      setMessage("Ажил дараалалд орлоо");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const label = status?.state === "queued" ? "Дараалалд…" : status?.running ? "Ажиллаж байна…" : buttonLabel;
  const log = status?.state === "queued" ? `Дараалалд байна (өмнө нь ${status.ahead} ажил)…` : status?.log.join("\n") || "—";

  return (
    <section className="rounded-[14px] bg-panel px-[22px] py-5">
      <div className="flex flex-wrap items-center gap-4">
        <h2 className="grow text-[15px] font-semibold">{title}</h2>
        <Button variant="primary" onClick={start} disabled={Boolean(status?.running)}>{label}</Button>
      </div>
      <p className="mt-4 text-sm leading-6 text-muted">{description}</p>
      <pre className="mt-4 max-h-48 overflow-auto rounded-[10px] bg-bg p-4 font-mono text-xs leading-5 whitespace-pre-wrap text-muted">{log}</pre>
      <div className="mt-3 min-h-5"><ActionStatus error={error} message={message} /></div>
    </section>
  );
}
