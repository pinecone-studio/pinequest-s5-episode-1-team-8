import type { Metadata } from "next";
import { LeadRow } from "@/components/leads/LeadRow";
import { EventsCard } from "@/components/leads/EventsCard";
import { StaffPin } from "@/components/leads/StaffPin";
import { EmptyState, PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
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
        sub="Бүртгүүлэх эсвэл ажилтантай ярих хүсэлт үлдээсэн хүмүүсийг эндээс хянана."
      />
      <Card className="mb-5">
        <StaffPin initial={people.staff_pin} />
      </Card>
      <Card className="mb-5">
        <EventsCard initial={people.events} />
      </Card>
      <Card>
        {leads.length ? (
          <Table head={["Хэзээ", "Нэр", "Утас", "Шалтгаан", "Төлөв", "Тэмдэглэл", "AI сануулга"]}>
            {leads.map((lead) => (
              <LeadRow
                key={lead.id}
                lead={lead}
                reminder={reminders.items[String(lead.id)]}
                code={people.codes[String(lead.id)]}
                changes={people.changes.filter((c) => c.lead_id === lead.id)}
              />
            ))}
          </Table>
        ) : (
          <EmptyState>Бүртгэл алга. Утсаар &quot;Бүртгүүлмээр байна&quot; гэж туршаарай.</EmptyState>
        )}
      </Card>
    </>
  );
}
