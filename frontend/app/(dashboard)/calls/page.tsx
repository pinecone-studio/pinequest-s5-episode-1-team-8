import type { Metadata } from "next";
import { CallsFilter, type CallsQuery } from "@/components/calls/CallsFilter";
import { CallsTable } from "@/components/calls/CallsTable";
import { EmptyState, PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Call } from "@/lib/types";

export const metadata: Metadata = { title: "Яриа" };

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export default async function CallsPage({ searchParams }: PageProps<"/calls">) {
  await requireUser();
  const sp = await searchParams;
  const value: CallsQuery = {
    q: one(sp.q).trim().slice(0, 100),
    days: ["1", "7", "30"].includes(one(sp.days)) ? one(sp.days) : "",
    unanswered: one(sp.unanswered) === "true",
  };
  const query = new URLSearchParams({ limit: "200" });
  if (value.q) query.set("q", value.q);
  if (value.days) query.set("days", value.days);
  if (value.unanswered) query.set("unanswered", "true");
  const calls = await apiGet<Call[]>(`/api/calls?${query}`);
  const filtered = Boolean(value.q || value.days || value.unanswered);

  return (
    <>
      <PageHeader title="Яриа" sub="Дуудлага бүр дээр дарж залгагч болон AI-ийн яриаг харна." />
      <CallsFilter value={value} />
      <Card>
        {filtered && !calls.length ? <EmptyState>Шүүлтүүрт тохирох дуудлага алга.</EmptyState> : <CallsTable calls={calls} />}
      </Card>
      {filtered && calls.length > 0 && <p className="mt-3 text-sm text-muted">{calls.length} дуудлага олдлоо</p>}
    </>
  );
}
