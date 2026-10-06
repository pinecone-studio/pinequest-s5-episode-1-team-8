import type { Metadata } from "next";
import { LeadRow } from "@/components/leads/LeadRow";
import { EmptyState, PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Lead } from "@/lib/types";

export const metadata: Metadata = { title: "Бүртгэл" };

export default async function LeadsPage() {
  await requireUser();
  const leads = await apiGet<Lead[]>("/api/leads");
  return (
    <>
      <PageHeader
        title="Бүртгэл"
        sub="Залгагчид бүртгүүлэх эсвэл ажилтантай ярих хүсэлт өгсөн. Утасны дугаарыг AI таахгүй — залгагч хэлж, баталгаажуулсан дугаар л харагдана. Баталгаажаагүй бол STT мөрөөс шалгана уу."
      />
      <Card>
        {leads.length ? (
          <Table head={["Хэзээ", "Нэр", "Утас", "Шалтгаан", "Төлөв", "Тэмдэглэл"]}>
            {leads.map((lead) => <LeadRow key={lead.id} lead={lead} />)}
          </Table>
        ) : (
          <EmptyState>Бүртгэл алга. Утсаар &quot;Бүртгүүлмээр байна&quot; гэж туршаарай.</EmptyState>
        )}
      </Card>
    </>
  );
}
