import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NewTenantForm } from "@/components/admin/NewTenantForm";
import { TenantRow } from "@/components/admin/TenantRow";
import { EmptyState, PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { AdminTenant } from "@/lib/types";

export const metadata: Metadata = { title: "Байгууллагууд" };

export default async function AdminPage() {
  const user = await requireUser();
  if (user.role !== "admin") notFound();
  const tenants = await apiGet<AdminTenant[]>("/api/admin/tenants");
  return (
    <>
      <PageHeader
        title="Байгууллагууд"
        sub="Платформд бүртгүүлсэн бүх байгууллага. Эрхийг (төлбөр төлсний дараа) энд идэвхжүүлнэ. «Харах» дарахад тэр байгууллагын бүх хуудсыг харна."
      />
      <NewTenantForm />
      <Card>
        {tenants.length ? (
          <Table head={["Байгууллага", "Дугаар", "Хэрэглэгч", "Дуудлага", "Төлөв", "Эрх", ""]}>
            {tenants.map((t) => <TenantRow key={t.slug} t={t} />)}
          </Table>
        ) : (
          <EmptyState>Байгууллага алга</EmptyState>
        )}
      </Card>
    </>
  );
}
