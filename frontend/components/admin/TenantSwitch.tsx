"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiSend } from "@/lib/client";
import type { AdminTenant } from "@/lib/types";
import { refreshStatus } from "@/lib/useStatus";

/** Admin: өөр байгууллага руу сольж харах (sidebar-ын доод хэсэг). current — одоо харж буй slug. */
export function TenantSwitch({ tenants, current }: { tenants: AdminTenant[]; current: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function change(slug: string) {
    setPending(true);
    try {
      await apiSend("/api/admin/switch", "POST", { slug });
      router.push("/");
      router.refresh();
      void refreshStatus();
    } finally {
      setPending(false);
    }
  }

  return (
    <select
      aria-label="Байгууллага солих (admin)"
      title="Байгууллага солих (admin)"
      value={current}
      disabled={pending}
      onChange={(e) => change(e.target.value)}
      className="mt-2.5 w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none disabled:opacity-50"
    >
      {tenants.map((t) => (
        <option key={t.slug} value={t.slug}>{t.name}{t.extension ? ` (${t.extension})` : ""}</option>
      ))}
    </select>
  );
}
