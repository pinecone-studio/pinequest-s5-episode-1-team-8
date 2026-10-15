"use client";

import { formatDateTime } from "@/lib/format";
import type { Message } from "@/lib/types";

/** Дуудлагын яриаг TXT файлаар татах (хөтөч дээр файл үүсгэдэг тул client компонент) */
export function DownloadTranscriptButton({
  uuid,
  createdAt,
  phone,
  duration,
  messages,
}: {
  uuid: string;
  createdAt: number;
  phone?: string | null;
  duration?: number | null;
  messages: Message[];
}) {
  const isDisabled = messages.length === 0;

  const handleDownload = () => {
    if (isDisabled) return;

    const header = [
      `Дуудлагын огноо: ${formatDateTime(createdAt)}`,
      `Залгагчийн дугаар: ${phone || "дугаар тодорхойгүй"}`,
      `Үргэлжилсэн хугацаа: ${duration != null ? `${duration} сек` : "тодорхойгүй"}`,
      "----------------------------------------",
      "",
    ].join("\n");
    const body = messages.map((m) => `${m.role === "user" ? "Залгагч" : "AI"}: ${m.text}`).join("\n");

    const url = URL.createObjectURL(new Blob([header + body], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `call-${uuid}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <button
      type="button"
      onClick={handleDownload}
      disabled={isDisabled}
      className={`cursor-pointer rounded-[10px] border border-line-2 px-3 py-1.5 text-sm font-semibold transition ${
        isDisabled ? "cursor-not-allowed bg-panel-2 text-muted opacity-50" : "bg-panel hover:border-brand hover:text-fg"
      }`}
    >
      TXT татах
    </button>
  );
}
