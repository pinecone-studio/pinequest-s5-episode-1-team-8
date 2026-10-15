import type { Metadata } from "next";
import { LeadsTable } from "@/components/leads/LeadsTable";
import { EventsCard } from "@/components/leads/EventsCard";
import { StaffPin } from "@/components/leads/StaffPin";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Lead, PeopleData, RemindersData } from "@/lib/types";

export const metadata: Metadata = { title: "Бүртгэлүүд" };

export default async function LeadsPage() {
  await requireUser();
  const [leads, reminders, people] = await Promise.all([
    apiGet<Lead[]>("/api/leads"),
    apiGet<RemindersData>("/api/reminders"),
    apiGet<PeopleData>("/api/people"),
  ]);
  return (
    <>
      <PageHeader
        title="Бүртгэлүүд"
        sub="Хөтөлбөр, эвентийн бүртгэл болон ажилтантай ярих хүсэлтийг тус тусад нь хянана."
      />
      <Card className="mb-5">
        <StaffPin initial={people.staff_pin} />
      </Card>
      <Card className="mb-5">
        <EventsCard initial={people.events} />
      </Card>
      <LeadsTable leads={leads} reminders={reminders} people={people} />
    </>
  );
}
