import type { Metadata } from "next";
import { NewTenantForm } from "@/components/admin/NewTenantForm";
import { TenantList } from "@/components/admin/TenantList";
import { PageHeader } from "@/components/PageHeader";
import { apiGet } from "@/lib/api";
import { requireAdmin } from "@/lib/session";
import type { AdminTenant } from "@/lib/types";

export const metadata: Metadata = { title: "Байгууллагууд" };

export default async function AdminPage() {
  await requireAdmin();
  const tenants = await apiGet<AdminTenant[]>("/api/admin/tenants");

  return (
    <>
      <PageHeader
        title="Байгууллагууд"
        sub="Платформд бүртгүүлсэн бүх байгууллага. Эрхийг (төлбөр төлсний дараа) энд идэвхжүүлнэ. «Харах» дарахад тэр байгууллагын бүх хуудсыг харна."
      />
      <NewTenantForm />
      <TenantList tenants={tenants} />
    </>
  );
}