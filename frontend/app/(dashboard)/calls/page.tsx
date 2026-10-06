import type { Metadata } from "next";
import { CallsTable } from "@/components/calls/CallsTable";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Call } from "@/lib/types";

export const metadata: Metadata = { title: "Яриа" };

export default async function CallsPage() {
  await requireUser();
  const calls = await apiGet<Call[]>("/api/calls?limit=200");
  return (
    <>
      <PageHeader title="Яриа" sub="Дуудлага бүр дээр дарж залгагч болон AI-ийн яриаг харна." />
      <Card>
        <CallsTable calls={calls} />
      </Card>
    </>
  );
}
