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

export default async function CallPage({ params }: PageProps<"/calls/[uuid]">) {
  await requireUser();
  const { uuid } = await params;
  const [{ call, messages }, answers] = await Promise.all([
    apiGet<CallDetail>(`/api/calls/${encodeURIComponent(uuid)}`),
    apiGet<TrainingAnswers>("/api/train/answers").catch(() => null), // AI сургалтгүй бол заах хэсэг харагдахгүй
  ]);

  return (
    <>
      <PageHeader
        title="Дуудлага"
        sub={`${formatDateTime(call.started_at)} · ${call.caller || "дугаар тодорхойгүй"} · ${formatSeconds(call.duration)}`}
        actions={<Link href="/calls" className="font-bold hover:underline">← Бүх яриа</Link>}
      />
      <Card>
        {messages.length ? (
          <div className="flex flex-col gap-3">
            {messages.map((m) => <ChatMessage key={m.id} m={m} answers={answers} />)}
          </div>
        ) : (
          <EmptyState>Яриа алга</EmptyState>
        )}
      </Card>
    </>
  );
}
