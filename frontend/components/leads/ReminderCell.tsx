"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import { REMINDER_STATUS, type Lead, type Reminder } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const INPUT = "rounded-[10px] border-[1.5px] border-line-2 bg-bg px-2.5 py-1.5 text-sm focus:border-brand focus:outline-none";

/** "2026-10-15T10:00" -> "10.15 10:00" (locale-гүй: hydration) */
const short = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)} ${iso.slice(11, 16)}`;

function tomorrow() {
  const d = new Date(Date.now() + 86_400_000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Бүртгэлийн мөрөнд: уулзалт товлох -> AI залгаж баталгаажуулна (GSM gateway / SIP trunk) */
export function ReminderCell({ lead, reminder }: { lead: Lead; reminder?: Reminder }) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("10:00");
  const [when, setWhen] = useState("day_before");
  const { pending, error, message, run } = useAction();
  const hasPhone = Boolean(lead.phone || (lead.caller && lead.caller.replace(/\D/g, "").length >= 8));

  function schedule() {
    void run(async () => {
      const r = await apiSend<Reminder>(`/api/reminders/${lead.id}`, "PUT", { appointment: `${date || tomorrow()}T${time}`, call: when });
      setOpen(false);
      return r;
    }, when === "now" ? "Дараалалд орлоо — AI удахгүй залгана" : "Товлогдлоо ✓");
  }

  if (!reminder && !open) {
    return hasPhone
      ? <Button onClick={() => { setDate(tomorrow()); setOpen(true); }}>📅 Уулзалт товлох</Button>
      : <span className="text-[13px] text-muted">дугааргүй</span>;
  }

  if (open) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-2">
          <input type="date" aria-label="Огноо" value={date} onChange={(e) => setDate(e.target.value)} className={INPUT} />
          <input type="time" aria-label="Цаг" value={time} onChange={(e) => setTime(e.target.value)} className={INPUT} />
        </div>
        <select aria-label="Хэзээ залгах" value={when} onChange={(e) => setWhen(e.target.value)} className={INPUT}>
          <option value="day_before">AI өмнөх өдрийн 11:00-д залгана</option>
          <option value="now">AI одоо залгана</option>
        </select>
        <div className="flex gap-2">
          <Button variant="primary" onClick={schedule} disabled={pending || !date}>Товлох</Button>
          <Button onClick={() => setOpen(false)}>Болих</Button>
        </div>
        <ActionStatus error={error} message={message} />
      </div>
    );
  }

  const r = reminder!;
  const [label, tone] = REMINDER_STATUS[r.status] ?? [r.status, "gray"];
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <Tag tone={tone}>{label}</Tag>
        <span className="font-mono text-sm">{short(r.appointment)}</span>
      </div>
      <div className="text-[13px] text-muted">
        {r.status === "scheduled" ? `AI залгах: ${formatDateTime(r.call_at)}` : r.attempts ? `${r.attempts} удаа залгасан` : ""}
        {r.status === "scheduled" && r.last_outcome ? ` · өмнөх: ${REMINDER_STATUS[r.last_outcome as keyof typeof REMINDER_STATUS]?.[0] ?? r.last_outcome}` : ""}
      </div>
      <details className="text-[13px] text-muted">
        <summary className="cursor-pointer hover:text-fg">AI-ийн хэлэх үг</summary>
        <p className="mt-1 max-w-[320px] leading-5">{r.text}</p>
      </details>
      <div className="flex flex-wrap gap-2">
        {r.status !== "calling" && <Button onClick={() => void run(() => apiSend(`/api/reminders/${lead.id}/call`, "POST"), "Дараалалд орлоо — AI удахгүй залгана")} disabled={pending}>📞 Одоо залгах</Button>}
        {r.status !== "calling" && <Button className="text-danger" onClick={() => void run(() => apiSend(`/api/reminders/${lead.id}`, "DELETE"), "Цуцаллаа")} disabled={pending}>Цуцлах</Button>}
      </div>
      <ActionStatus error={error} message={message} />
    </div>
  );
}
