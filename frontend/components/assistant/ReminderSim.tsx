"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { LeadChange, Person } from "@/lib/types";
import type { RosterItem } from "./AssistantChat";

type CallReply = { replies: string[]; person: Person; changes: LeadChange[] };

/** Эвентийн өмнөх өдрийн "ирэх үү" дуудлагыг утасгүй турших (бодит дуудлагын үр дүнгийн логикоор) */
export function ReminderSim({ roster, onResult }: { roster: RosterItem[]; onResult: (r: CallReply, lines: string[]) => void }) {
  const events = roster.filter((p) => p.course && /эвент|event|hackathon/i.test(p.course) && p.status !== "canceled");
  const [leadId, setLeadId] = useState<number | "">("");
  const [ringing, setRinging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const id = leadId || events[0]?.id;

  async function call(key?: "1" | "2") {
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      const r = await apiSend<CallReply>("/api/assistant/reminder-call", "POST", { lead_id: id, key: key ?? null });
      onResult(r, key ? [`[товчлуур] ${key}`, ...r.replies.map((x) => `📞 ${x}`)] : r.replies.map((x) => `📞 ${x}`));
      setRinging(!key);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Алдаа гарлаа");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[12px] bg-panel px-4 py-3">
      <div className="mb-2 text-[13px] text-muted">📞 Эвентийн өмнөх өдрийн дуудлага (AI өөрөө залгана — туршилт)</div>
      {events.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Хэн рүү"
            value={id ?? ""}
            onChange={(e) => { setLeadId(Number(e.target.value)); setRinging(false); }}
            className="rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none"
          >
            {events.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.course}</option>)}
          </select>
          {ringing ? (
            <>
              <Button variant="primary" onClick={() => call("1")} disabled={busy}>1 — ирнэ</Button>
              <Button onClick={() => call("2")} disabled={busy}>2 — ирэхгүй</Button>
            </>
          ) : (
            <Button onClick={() => call()} disabled={busy}>AI залгах</Button>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted">Эвентэд бүртгүүлсэн хүн алга. «+ Жишээ бүртгэл» дарна уу.</p>
      )}
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </div>
  );
}
