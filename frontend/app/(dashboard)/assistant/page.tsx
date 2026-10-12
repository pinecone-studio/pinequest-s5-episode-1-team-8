import type { Metadata } from "next";
import { AssistantChat } from "@/components/assistant/AssistantChat";
import { PageHeader } from "@/components/PageHeader";
import { apiGet } from "@/lib/api";
import { requireAdmin } from "@/lib/session";
import type { Lead, PeopleData } from "@/lib/types";

export const metadata: Metadata = { title: "AI туршилт" };

export default async function AssistantPage() {
  await requireAdmin();
  const [leads, people] = await Promise.all([apiGet<Lead[]>("/api/leads"), apiGet<PeopleData>("/api/people")]);
  const roster = leads
    .filter((l) => l.reason === "lead")
    .map((l) => ({ id: l.id, name: l.name, course: l.course, status: l.status, code: people.codes[String(l.id)] ?? "" }));
  return (
    <>
      <PageHeader
        title="AI туршилт"
        sub="Утасгүйгээр AI ресепшнтэй бичиж, товчлуур дарж ярина. Хүн бүртгэлийн кодоороо өөрийн бүртгэлийг (хөтөлбөр, эвент, цаг, дугаар) цуцалж, өөрчилнө; ажилтан ажилтны кодоор бусдын бүртгэлийг. AI зөвхөн тухайн хүний баримтаас хайж (хувийн RAG), баталгаажуулсны дараа өгөгдлийн санд бичнэ."
      />
      <AssistantChat roster={roster} staffPin={people.staff_pin} />
    </>
  );
}
