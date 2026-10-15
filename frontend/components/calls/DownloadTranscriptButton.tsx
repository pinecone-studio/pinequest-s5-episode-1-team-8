"use client";

import { formatDateTime } from "@/lib/format";
import type { Message } from "@/lib/types";

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
  const isDisabled = !messages || messages.length === 0;

  const handleDownload = () => {
    if (isDisabled) return;

    const formattedDate = formatDateTime(createdAt);
    const displayPhone = phone ? phone : "дугаар тодорхойгүй";
    const displayDuration = duration != null ? `${duration} сек` : "тодорхойгүй";

    const header = [
      `Дуудлагын огноо: ${formattedDate}`,
      `Залгагчийн дугаар: ${displayPhone}`,
      `Үргэлжилсэн хугацаа: ${displayDuration}`,
      "----------------------------------------",
      "",
    ].join("\n");

    const body = messages
      .map((msg) => {
        const roleLabel = msg.role === "user" ? "Залгагч" : "AI";
        return `${roleLabel}: ${msg.text}`;
      })
      .join("\n");

    const content = header + body;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);

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
        isDisabled
          ? "opacity-50 cursor-not-allowed bg-panel-2 text-muted"
          : "bg-panel hover:border-brand hover:text-fg"
      }`}
    >
      TXT татах
    </button>
  );
}
