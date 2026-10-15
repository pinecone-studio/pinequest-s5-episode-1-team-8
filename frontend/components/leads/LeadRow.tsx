"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ActionStatus } from "@/components/ui/Alert";
import { Td } from "@/components/ui/Table";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import { LEAD_STATUS, type Lead, type LeadChange, type LeadStatus, type Reminder } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { ForgetPerson } from "./ForgetPerson";
import { LeadChanges } from "./LeadChanges";
import { ReminderCell } from "./ReminderCell";

const CONTROL =
  "w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none disabled:opacity-50";

/** Бүртгэлийн нэг мөр: төлөв солих, тэмдэглэл бичих (талбараас гарахад хадгална), AI сануулга,
-  бүртгэлийн код ба залгагч утсаар хийсэн өөрчлөлтүүд (хувийн RAG) */
export function LeadRow({ lead, reminder, code, changes = [] }: { lead: Lead; reminder?: Reminder; code?: string; changes?: LeadChange[] }) {
  const { pending, error, message, run } = useAction();
  const save = (body: { status?: LeadStatus; notes?: string; name?: string }) =>
    run(() => apiSend(`/api/leads/${lead.id}`, "PATCH", body), "Хадгаллаа ✓");

  const [phoneCopied, setPhoneCopied] = useState(false);
  const [phoneError, setPhoneError] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);
  const [codeError, setCodeError] = useState(false);

  useEffect(() => {
    if (!phoneCopied && !phoneError) return;
    const timer = setTimeout(() => {
      setPhoneCopied(false);
      setPhoneError(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, [phoneCopied, phoneError]);

  useEffect(() => {
    if (!codeCopied && !codeError) return;
    const timer = setTimeout(() => {
      setCodeCopied(false);
      setCodeError(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, [codeCopied, codeError]);

  const handleCopyPhone = async () => {
    if (!lead.phone) return;
    setPhoneError(false);
    try {
      await navigator.clipboard.writeText(lead.phone);
      setPhoneCopied(true);
    } catch {
      setPhoneError(true);
    }
  };

  const handleCopyCode = async () => {
    if (!code) return;
    setCodeError(false);
    try {
      await navigator.clipboard.writeText(code);
      setCodeCopied(true);
    } catch {
      setCodeError(true);
    }
  };

  return (
    <tr>
      <Td>
        <span className="font-mono text-sm">{formatDateTime(lead.created_at)}</span>
        <div><Link href={`/calls/${lead.call_uuid}`} className="text-[13px] text-muted hover:underline">яриа</Link></div>
      </Td>
      <Td className="min-w-[240px]">
        {/* Нэрийг засвал AI нэрсийн толиндоо нэмж, дараагийн удаа зөв таньна */}
        <input
          aria-label="Нэр"
          defaultValue={lead.name ?? ""}
          placeholder="Нэр"
          maxLength={80}
          onBlur={(e) => {
            const name = e.target.value.trim();
            if (name && name !== (lead.name ?? "")) save({ name });
          }}
          title="Нэрийг засвал AI дараагийн удаа зөв таньна"
          className={`${CONTROL} font-semibold`}
        />
        {code && (
          <div className="text-[13px] text-muted flex items-center gap-2 flex-wrap mt-1">
            <span>Код <b className="font-mono text-fg">{code}</b></span>
            <button
              type="button"
              onClick={handleCopyCode}
              className="rounded bg-panel-2 px-1.5 py-0.5 text-[11px] font-medium text-muted hover:text-fg border border-line-2 transition cursor-pointer"
              title={codeError ? "Хуулж чадсангүй" : "Код хуулах"}
            >
              <span aria-live="polite">{codeError ? "Хуулж чадсангүй" : codeCopied ? "Хууллаа ✓" : "Хуулах"}</span>
            </button>
          </div>
        )}
        <LeadChanges changes={changes} />
        <ForgetPerson leadId={lead.id} name={lead.name} />
      </Td>
      <Td>
        {lead.phone ? (
          <div className="flex items-center gap-2 flex-wrap">
            <b className="font-mono">{lead.phone}</b>
            <button
              type="button"
              onClick={handleCopyPhone}
              className="rounded bg-panel-2 px-1.5 py-0.5 text-[11px] font-medium text-muted hover:text-fg border border-line-2 transition cursor-pointer"
              title={phoneError ? "Хуулж чадсангүй" : "Утас хуулах"}
            >
              <span aria-live="polite">{phoneError ? "Хуулж чадсангүй" : phoneCopied ? "Хууллаа ✓" : "Хуулах"}</span>
            </button>
          </div>
        ) : (
          <Tag tone="bad">дугааргүй</Tag>
        )}
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
      <Td className="min-w-[230px]">
        <ReminderCell lead={lead} reminder={reminder} />
      </Td>
    </tr>
  );
}