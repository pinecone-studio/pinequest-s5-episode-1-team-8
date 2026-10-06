import type { ReactNode } from "react";
import { ViewingBanner } from "@/components/admin/ViewingBanner";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { AdminTenant, Status } from "@/lib/types";

// Нэвтэрсний дараах бүх хуудас: зүүн талд sidebar, баруун талд хуудас
export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();
  // AI/SIP төлөв, тоон тэмдгийн анхны утга. Цаашид хөтөч 10с тутам өөрөө асууна (lib/useStatus.ts).
  // Admin: sidebar-ын байгууллага солих жагсаалт
  const [status, tenants] = await Promise.all([
    apiGet<Status>("/api/status").catch(() => null),
    user.role === "admin" ? apiGet<AdminTenant[]>("/api/admin/tenants").catch(() => null) : null,
  ]);
  return (
    <div className="flex min-h-screen max-md:flex-col">
      <Sidebar user={user} status={status} tenants={tenants} />
      <main className="max-w-[1500px] min-w-0 flex-1 px-16 pt-[46px] pb-16 max-xl:px-7 max-xl:pt-8 max-md:px-4 max-md:pt-6">
        {user.own_tenant === false && <ViewingBanner name={user.tenant_name} />}
        {children}
      </main>
    </div>
  );
}
