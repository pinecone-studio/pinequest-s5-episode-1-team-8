"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Td } from "@/components/ui/Table";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import { PLAN_LABEL, type AdminTenant, type Plan } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { refreshStatus } from "@/lib/useStatus";

/** Байгууллагын нэг мөр: эрх солих, "Харах" (тэр байгууллага руу сольж бүх хуудсыг харах) */
export function TenantRow({ t }: { t: AdminTenant }) {
  const router = useRouter();
  const { pending, error, message, run } = useAction();
  const [switching, setSwitching] = useState(false);

  async function view() {
    setSwitching(true);
    await run(() => apiSend("/api/admin/switch", "POST", { slug: t.slug }), "");
    router.push("/");
    router.refresh();
    void refreshStatus();
  }

  return (
    <tr>
      <Td>
        <b>{t.name}</b>
        {t.address ? (
          <div className="text-[13px] text-muted">
            <span className="font-semibold">Хаяг:</span> {t.address} · {formatDateTime(t.created_at)}
          </div>
        ) : (
          <div className="font-mono text-[13px] text-muted">{t.slug} · {formatDateTime(t.created_at)}</div>
        )}
        {t.email && (
          <div className="text-[13px] text-muted">
            <span className="font-semibold">И-мэйл:</span> {t.email}
          </div>
        )}
      </Td>
      <Td className="font-mono text-sm">{t.extension ?? "—"}</Td>
      <Td className="text-[13px] text-muted">{t.users.map((u) => <div key={u}>{u}</div>)}</Td>
      <Td className="font-mono text-sm">{t.calls}</Td>
      <Td>
        <div className="flex flex-wrap gap-1.5">
          {t.ready ? <Tag>Бэлэн</Tag> : <Tag tone="gray">Бэлдээгүй</Tag>}
          {t.job !== "idle" && <Tag tone={t.job === "error" ? "bad" : "warn"}>{t.job}</Tag>}
        </div>
      </Td>
      <Td className="min-w-[150px]">
        <select
          aria-label={`${t.name} — эрх`}
          defaultValue={t.plan}
          disabled={pending}
          onChange={(e) => run(() => apiSend("/api/admin/plan", "POST", { slug: t.slug, plan: e.target.value as Plan }))}
          className="w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none"
        >
          {Object.entries(PLAN_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <div className="mt-1 min-h-5"><ActionStatus error={error} message={message} /></div>
      </Td>
      <Td>
        <Button type="button" onClick={view} disabled={switching}>Харах</Button>
      </Td>
    </tr>
  );
}
