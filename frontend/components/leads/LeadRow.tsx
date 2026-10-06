"use client";

import Link from "next/link";
import { ActionStatus } from "@/components/ui/Alert";
import { Td } from "@/components/ui/Table";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import { LEAD_STATUS, type Lead, type LeadStatus } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const CONTROL =
  "w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none disabled:opacity-50";

/** Бүртгэлийн нэг мөр: төлөв солих, тэмдэглэл бичих (талбараас гарахад хадгална) */
export function LeadRow({ lead }: { lead: Lead }) {
  const { pending, error, message, run } = useAction();
  const save = (body: { status?: LeadStatus; notes?: string }) =>
    run(() => apiSend(`/api/leads/${lead.id}`, "PATCH", body), "Хадгаллаа ✓");

  return (
    <tr>
      <Td>
        <span className="font-mono text-sm">{formatDateTime(lead.created_at)}</span>
        <div><Link href={`/calls/${lead.call_uuid}`} className="text-[13px] text-muted hover:underline">яриа</Link></div>
      </Td>
      <Td>{lead.name || "—"}</Td>
      <Td>
        {lead.phone ? <b className="font-mono">{lead.phone}</b> : <Tag tone="bad">дугааргүй</Tag>}
        {lead.phone_raw && <div className="text-[13px] text-muted">STT: {lead.phone_raw}</div>}
        {lead.caller && <div className="text-[13px] text-muted">Caller ID: {lead.caller}</div>}
      </Td>
      <Td>
        {lead.reason === "handoff" ? <Tag tone="warn">Ажилтан</Tag> : <Tag>Бүртгүүлэх</Tag>}
        {lead.question && <div className="mt-1 text-[13px] text-muted">{lead.question}</div>}
      </Td>
      <Td className="min-w-[150px]">
        <select
          aria-label="Төлөв"
          defaultValue={lead.status}
          disabled={pending}
          onChange={(e) => save({ status: e.target.value as LeadStatus })}
          className={CONTROL}
        >
          {Object.entries(LEAD_STATUS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </Td>
      <Td className="min-w-[220px]">
        <input
          aria-label="Тэмдэглэл"
          defaultValue={lead.notes ?? ""}
          placeholder="Тэмдэглэл"
          maxLength={1000}
          onBlur={(e) => e.target.value.trim() !== (lead.notes ?? "") && save({ notes: e.target.value })}
          className={CONTROL}
        />
        <div className="mt-1 min-h-5"><ActionStatus error={error} message={message} /></div>
      </Td>
    </tr>
  );
}
