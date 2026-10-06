import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/ui/Card";
import { Tag } from "@/components/ui/Tag";
import { formatDateTime } from "@/lib/format";
import { requireUser } from "@/lib/session";
import { PLAN_LABEL, ROLE_LABEL } from "@/lib/types";

export const metadata: Metadata = { title: "Самбар" };

export default async function DashboardPage() {
  const user = await requireUser();
  return (
    <>
      <PageHeader title="Самбар" sub="Дуудлага, хариулсан хувь, AI-ийн төлөв энд харагдана." />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3.5">
        <StatCard label="Нэвтэрсэн хэрэглэгч">{user.email}</StatCard>
        <StatCard label="Эрх">
          <Tag tone={user.role === "admin" ? "warn" : "ok"}>{ROLE_LABEL[user.role]}</Tag>
        </StatCard>
        <StatCard label="Байгууллага">{user.tenant_name}</StatCard>
        <StatCard label="Дотуур дугаар">
          <span className="font-mono">{user.extension ?? "—"}</span>
        </StatCard>
        <StatCard label="Эрхийн төлөв">
          <Tag tone={user.plan === "active" ? "ok" : user.plan === "suspended" ? "bad" : "gray"}>{PLAN_LABEL[user.plan]}</Tag>
        </StatCard>
        <StatCard label="Нэвтрэлт дуусах">{formatDateTime(user.expires)}</StatCard>
      </div>
    </>
  );
}
