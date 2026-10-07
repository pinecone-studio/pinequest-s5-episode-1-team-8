"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { EventItem } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const INPUT = "rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none";
const short = (iso: string) => `${iso.slice(5, 7)}.${iso.slice(8, 10)} ${iso.slice(11, 16)}`;

/** Эвентүүд: нэг удаа оруулна — бүртгүүлсэн хүн бүрт өмнөх өдрийн 11:00-д AI "ирэх үү" гэж автоматаар залгана */
export function EventsCard({ initial }: { initial: EventItem[] }) {
  const [events, setEvents] = useState(initial);
  const [name, setName] = useState("");
  const [at, setAt] = useState("");
  const { pending, error, message, run } = useAction();

  const [scheduled, setScheduled] = useState(0);
  const save = (next: EventItem[], ok: string) =>
    run(async () => {
      const r = await apiSend<{ events: EventItem[]; scheduled: number }>("/api/people/events", "PUT", { events: next });
      setEvents(r.events);
      setScheduled(r.scheduled);
    }, ok);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-[13px] uppercase tracking-wider text-muted">Эвентүүд</div>
        <p className="text-[13px] text-muted">Бүртгүүлсэн хүн бүрт өмнөх өдрийн 11:00-д AI «ирэх үү» гэж залгаж, хариуг хувийн RAG-д тэмдэглэнэ.</p>
      </div>
      {events.length > 0 && (
        <ul className="mb-3 space-y-1.5 text-sm">
          {events.map((e) => (
            <li key={`${e.name}-${e.at}`} className="flex items-center justify-between gap-3 rounded-lg bg-bg px-3 py-2">
              <span><b>{e.name}</b> <span className="font-mono text-muted">· {short(e.at)}</span></span>
              <button type="button" disabled={pending} onClick={() => save(events.filter((x) => x !== e), "Устгалаа")}
                className="cursor-pointer text-[13px] text-muted hover:text-danger">Устгах</button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <input aria-label="Эвентийн нэр" placeholder="Эвентийн нэр (бүртгэлийн нэртэй ижил)" value={name}
          onChange={(e) => setName(e.target.value)} className={`${INPUT} min-w-[240px] flex-1`} />
        <input aria-label="Огноо, цаг" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} className={INPUT} />
        <Button
          disabled={pending || name.trim().length < 2 || !at}
          onClick={() => save([...events, { name: name.trim(), at }], "Нэмлээ").then((ok) => ok && (setName(""), setAt("")))}
        >
          + Эвент
        </Button>
      </div>
      <div className="mt-1 min-h-5">
        <ActionStatus error={error} message={message && scheduled ? `${message} · ${scheduled} хүнд дуудлага товлогдлоо` : message} />
      </div>
    </div>
  );
}
