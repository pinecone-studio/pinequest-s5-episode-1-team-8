import type { Metadata } from "next";
import Link from "next/link";
import { CallsTable } from "@/components/calls/CallsTable";
import { RouteTag } from "@/components/calls/RouteTag";
import { AnswerRate } from "@/components/dashboard/AnswerRate";
import { CallsByDay } from "@/components/dashboard/CallsByDay";
import { RouteBreakdown } from "@/components/dashboard/RouteBreakdown";
import { SetupBanner } from "@/components/dashboard/SetupBanner";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { requireUser } from "@/lib/session";
import type { Call, Stats, Status, Unanswered } from "@/lib/types";

export const metadata: Metadata = { title: "Самбар" };

export default async function DashboardPage() {
  await requireUser();
  const [stats, calls, unanswered, status] = await Promise.all([
    apiGet<Stats>("/api/stats"),
    apiGet<Call[]>("/api/calls?limit=6"),
    apiGet<Unanswered[]>("/api/unanswered?limit=5"),
    apiGet<Status>("/api/status"),
  ]);

  return (
    <>
      {!status.ready && <SetupBanner />}
      <PageHeader
        title="Сайн байна уу 👋"
        note={
          <span className={status.ai_server ? "text-brand" : "text-danger"}>
            {" · "}AI ресепшн {status.ai_server ? "онлайн" : "унтарсан"}
          </span>
        }
        actions={
          <>
            <Link href="/knowledge" className="font-bold hover:underline">Мэдээлэл нэмэх →</Link>
            <Link
              href="/unanswered"
              className="rounded-[10px] bg-brand px-[26px] py-[15px] font-semibold text-[#07130c] hover:bg-brand-2"
            >
              {stats.unanswered ? `${stats.unanswered} асуулт шалгах` : "Шалгах зүйл алга"}
            </Link>
          </>
        }
      />

      <section className="mb-[34px] grid grid-cols-[1.4fr_1fr_.9fr] gap-16 border-b border-line pb-[34px] max-xl:grid-cols-1 max-xl:gap-[34px]">
        <AnswerRate stats={stats} />
        <RouteBreakdown routes={stats.routes} />
        <CallsByDay days={stats.days} />
      </section>

      <Section title="Сүүлийн дуудлагууд" aside={<Link href="/calls" className="hover:underline">Бүгдийг харах</Link>}>
        <Card>
          <CallsTable calls={calls} />
        </Card>
      </Section>

      <Section title="Хариулж чадаагүй асуултууд" aside={<Link href="/unanswered" className="hover:underline">Бүгдийг харах</Link>}>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3.5">
          {unanswered.length ? (
            unanswered.map((u) => (
              <Link key={u.id} href={`/calls/${u.call_uuid}`} className="rounded-[14px] bg-panel px-[22px] py-5 hover:bg-panel-2">
                <div className="mb-2.5 font-semibold">“{u.question}”</div>
                <RouteTag route={u.route} />
                <div className="mt-2 font-mono text-[13px] text-muted">{formatDateTime(u.ts)}</div>
              </Link>
            ))
          ) : (
            <Card>
              <div className="text-[34px] font-extrabold">0</div>
              <div className="text-sm text-muted">Бүх асуултад хариулсан</div>
            </Card>
          )}
          <Link href="/knowledge" className="rounded-[14px] bg-panel px-[22px] py-5 hover:bg-panel-2">
            <div className="text-[34px] font-extrabold">{status.facts}</div>
            <div className="text-sm text-muted">Аудиотой өгүүлбэр</div>
          </Link>
          <Link href="/faq" className="rounded-[14px] bg-panel px-[22px] py-5 hover:bg-panel-2">
            <div className="text-[34px] font-extrabold">{status.faq}</div>
            <div className="text-sm text-muted">Аудиотой FAQ</div>
          </Link>
          <Link href="/leads" className="rounded-[14px] bg-panel px-[22px] py-5 hover:bg-panel-2">
            <div className="text-[34px] font-extrabold">{stats.new_leads}</div>
            <div className="text-sm text-muted">Шинэ бүртгэл</div>
          </Link>
        </div>
      </Section>
    </>
  );
}
