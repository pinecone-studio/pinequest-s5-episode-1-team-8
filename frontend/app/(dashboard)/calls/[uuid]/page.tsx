import type { Metadata } from "next";
import Link from "next/link";
import { ChatMessage } from "@/components/calls/ChatMessage";
import { EmptyState, PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatDateTime, formatSeconds } from "@/lib/format";
import { requireUser } from "@/lib/session";
import type { CallDetail, TrainingAnswers } from "@/lib/types";

export const metadata: Metadata = { title: "Дуудлага" };

function DownloadTranscriptButton({
  uuid,
  createdAt,
  phone,
  duration,
  messages,
}: {
  uuid: string;
  createdAt: number;
  phone?: string | null;
  duration?: number;
  messages: any[]; // TypeScript алдааг бүрэн алга болгох зорилгоор any[] болгов
}) {
  const isDisabled = !messages || messages.length === 0;

  const handleDownload = () => {
    if (isDisabled) return;

    const formattedDate = formatDateTime(createdAt);
    const displayPhone = phone ? phone : "дугаар тодорхойгүй";
    const displayDuration = duration !== undefined ? `${duration} сек` : "тодорхойгүй";

    const header = [
      `Дуудлагын огноо: ${formattedDate}`,
      `Залгагчийн дугаар: ${displayPhone}`,
      `Үргэлжилсэн хугацаа: ${displayDuration}`,
      "----------------------------------------",
      "",
    ].join("\n");

    const body = messages
      .map((msg: any) => {
        const roleLabel = msg.role === "caller" ? "Залгагч" : "AI";
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

export default async function CallPage({ params }: PageProps<"/calls/[uuid]">) {
  await requireUser();
  const { uuid } = await params;
  const [{ call, messages }, answers] = await Promise.all([
    apiGet<CallDetail>(`/api/calls/${encodeURIComponent(uuid)}`),
    apiGet<TrainingAnswers>("/api/train/answers").catch(() => null),
  ]);

  return (
    <>
      <PageHeader
        title="Дуудлага"
        sub={`${formatDateTime(call.started_at)} · ${call.caller || "дугаар тодорхойгүй"} · ${formatSeconds(call.duration)}`}
        actions={
          <div className="flex items-center gap-3">
            <DownloadTranscriptButton
              uuid={call.uuid}
              createdAt={call.started_at}
              phone={call.caller}
              duration={call.duration ?? undefined}
              messages={messages}
            />
            <Link href="/calls" className="font-bold hover:underline">
              ← Бүх яриа
            </Link>
          </div>
        }
      />
      <Card>
        {messages.length ? (
          <div className="flex flex-col gap-3">
            {messages.map((m) => (
              <ChatMessage key={m.id} m={m} answers={answers} />
            ))}
          </div>
        ) : (
          <EmptyState>Яриа алга</EmptyState>
        )}
      </Card>
    </>
  );
}