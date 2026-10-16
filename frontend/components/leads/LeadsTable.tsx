"use client";

import { useState } from "react";
import { EmptyState } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import type { Lead, PeopleData, RemindersData } from "@/lib/types";
import { LeadRow } from "./LeadRow";

const GROUPS = [
  { reason: "lead", title: "Хөтөлбөрийн бүртгэл", empty: "Хөтөлбөрийн бүртгэл алга." },
  { reason: "event", title: "Эвентийн бүртгэл", empty: "Эвентийн бүртгэл алга." },
  { reason: "handoff", title: "Ажилтантай ярих хүсэлт", empty: "Ажилтантай ярих хүсэлт алга." },
] as const;

export function LeadsTable({ leads, reminders, people }: { leads: Lead[]; reminders: RemindersData; people: PeopleData }) {
  const [reason, setReason] = useState<Lead["reason"]>("lead");
  const group = GROUPS.find((item) => item.reason === reason)!;
  const rows = leads.filter((lead) => lead.reason === reason);

  return (
    <Card>
      <label className="mb-5 flex flex-wrap items-center gap-3 text-sm font-medium">
        Бүртгэлийн төрөл
        <select
          value={reason}
          onChange={(event) => setReason(event.target.value as Lead["reason"])}
          className="rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2.5 text-fg focus:border-brand focus:outline-none"
        >
          {GROUPS.map((item) => (
            <option key={item.reason} value={item.reason}>
              {item.title} ({leads.filter((lead) => lead.reason === item.reason).length})
            </option>
          ))}
        </select>
      </label>
      <h2 className="mb-4 text-xl font-semibold">{group.title} ({rows.length})</h2>
      {rows.length ? (
        <Table head={["Хэзээ", "Нэр", "Утас", "Хөтөлбөр / эвент", "Төлөв", "Тэмдэглэл", "AI сануулга"]}>
          {rows.map((lead) => (
            <LeadRow
              key={lead.id}
              lead={lead}
              reminder={reminders.items[String(lead.id)]}
              code={people.codes[String(lead.id)]}
              changes={people.changes.filter((change) => change.lead_id === lead.id)}
            />
          ))}
        </Table>
      ) : <EmptyState>{group.empty}</EmptyState>}
    </Card>
  );
}
