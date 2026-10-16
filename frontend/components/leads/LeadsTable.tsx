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
  // Хамгийн сүүлийн бүртгэлийн төрлөөр нээнэ (эвентэд бүртгүүлсэн бол "Эвентийн бүртгэл")
  const newest = leads.reduce<Lead | undefined>((a, b) => (!a || b.created_at > a.created_at ? b : a), undefined);
  const [reason, setReason] = useState<Lead["reason"]>(newest?.reason ?? "lead");
  const group = GROUPS.find((item) => item.reason === reason)!;
  const rows = leads.filter((lead) => lead.reason === reason);

  return (
    <Card>
      <div role="tablist" aria-label="Бүртгэлийн төрөл" className="mb-5 flex flex-wrap gap-2">
        {GROUPS.map((item) => {
          const all = leads.filter((lead) => lead.reason === item.reason);
          const fresh = all.filter((lead) => lead.status === "new").length;   // sidebar-ын "шинэ" badge-тэй ижил
          const active = item.reason === reason;
          return (
            <button
              key={item.reason}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setReason(item.reason)}
              className={`flex items-center gap-2 rounded-[10px] border-[1.5px] bg-bg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                active ? "border-brand font-semibold text-fg" : "border-line-2 text-muted hover:bg-panel-2"
              }`}
            >
              {item.title} ({all.length})
              {fresh > 0 && (
                <b className="rounded-[10px] bg-warn px-[7px] font-mono text-[11px] leading-[18px] font-semibold text-[#1b1408]"
                  aria-label={`${fresh} шинэ`}>
                  {fresh}
                </b>
              )}
            </button>
          );
        })}
      </div>
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
