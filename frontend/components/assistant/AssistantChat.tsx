"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import { LEAD_STATUS, type AssistantReply, type LeadChange, type LeadStatus, type Person, type RagHit } from "@/lib/types";
import { Keypad } from "./Keypad";
import { RagPanel } from "./RagPanel";
import { ReminderSim } from "./ReminderSim";

type Msg = { who: "user" | "ai"; text: string };
type Mode = "caller" | "staff";
export type RosterItem = { id: number; name: string | null; course: string | null; status: LeadStatus; code: string };

const EXAMPLES: Record<Mode, string[]> = {
  caller: ["Эвентэд очиж чадахгүй боллоо", "Бүртгэлээ цуцалмаар байна", "Цагаа солимоор байна", "Би юунд бүртгүүлсэн бэ",
    "Би дугаараа сольсон", "Эвентэд ирнэ гэж бүртгэгдсэн үү", "Сургалтын төлбөр хэд vэ"],
  staff: ["Болдын цагийг Баасан гараг руу шилжүүл", "Номины бүртгэлийг цуцал", "Сараагийн дугаарыг солих"],
};
const NEED_KEYPAD = new Set(["code", "staff_code", "target", "target_confirm", "new_phone", "phone_confirm", "slot",
  "slot_confirm", "cancel_confirm", "reg_cancel_confirm", "menu"]);

/** "AI туршилт": чат + товчлуур (зүүн), хувийн RAG / хайлт / өгөгдлийн сан (баруун) */
export function AssistantChat({ roster, staffPin }: { roster: RosterItem[]; staffPin: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("caller");
  const [session, setSession] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [state, setState] = useState("idle");
  const [need, setNeed] = useState(0);
  const [person, setPerson] = useState<Person | null>(null);
  const [trace, setTrace] = useState<RagHit[]>([]);
  const [changes, setChanges] = useState<LeadChange[]>([]);
  const [changed, setChanged] = useState<Set<string>>(new Set());
  
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const userScrolledRef = useRef(false);

  // Auto-resize textarea (1 to 5 lines)
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const newHeight = Math.min(ta.scrollHeight, 120); // ~5 lines max
    ta.style.height = `${newHeight}px`;
  }, [text]);

  const handleScroll = () => {
    const el = chatContainerRef.current;
    if (!el) return;
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    if (isAtBottom) {
      userScrolledRef.current = false;
      setShowScrollBottom(false);
    } else {
      userScrolledRef.current = true;
      setShowScrollBottom(true);
    }
  };

  useEffect(() => {
    const el = chatContainerRef.current;
    if (!el) return;
    if (!userScrolledRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [msgs]);

  const scrollToBottom = () => {
    const el = chatContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    userScrolledRef.current = false;
    setShowScrollBottom(false);
  };

  async function send(body: { text?: string; dtmf?: string }, shown: string | null, m: Mode = mode, sid = session) {
    setBusy(true);
    setError("");
    if (shown) setMsgs((x) => [...x, { who: "user", text: shown }]);
    try {
      const r = await apiSend<AssistantReply>("/api/assistant", "POST", { session: sid, mode: m, ...body });
      setSession(r.session);
      setMsgs((x) => [...x, ...r.replies.map((t) => ({ who: "ai" as const, text: t }))]);
      setState(r.state);
      setNeed(r.dtmf_len);
      if (r.trace.length) setTrace(r.trace);
      if (r.person) setPerson(r.person);
      setChanged(new Set(r.changes.map((c) => c.field)));
      if (r.changes.length) {
        setChanges((x) => [...r.changes, ...x]);
        router.refresh();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Алдаа гарлаа");
    } finally {
      setBusy(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }

  function reset(m: Mode) {
    setMode(m);
    setSession(null);
    setMsgs([]);
    setState("idle");
    setNeed(0);
    setPerson(null);
    setTrace([]);
    setChanged(new Set());
    if (m === "staff") void send({}, null, "staff", null);
    setTimeout(() => textareaRef.current?.focus(), 50);
  }

  async function samples() {
    setBusy(true);
    try {
      await apiSend("/api/assistant/samples", "POST");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    void send({ text: t }, t);
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {(["caller", "staff"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => reset(m)}
              className={`cursor-pointer rounded-[10px] border-[1.5px] px-4 py-2 text-sm font-semibold ${mode === m ? "border-brand text-brand" : "border-line-2 text-muted hover:border-brand"}`}
            >
              {m === "caller" ? "📞 Залгагч (өөрийн бүртгэл)" : "🧑‍🏫 Ажилтан (бусдын бүртгэл)"}
            </button>
          ))}
          <button type="button" onClick={() => reset(mode)} className="ml-auto cursor-pointer text-sm text-muted hover:text-fg">
            ↺ Шинэ яриа
          </button>
        </div>

        <div className="relative rounded-[14px] bg-panel">
          <div
            ref={chatContainerRef}
            onScroll={handleScroll}
            role="log"
            aria-live="polite"
            aria-relevant="additions"
            className="h-[420px] space-y-2.5 overflow-y-auto px-5 py-4"
          >
            {!msgs.length && (
              <p className="text-sm text-muted">
                {mode === "caller"
                  ? "Залгагч шиг бичнэ үү. Жишээ нь «Эвентэд очиж чадахгүй боллоо» — AI кодыг тань асууж, зөвхөн таны бүртгэлийг өөрчилнө."
                  : "Ажилтны кодоо товчлуураар бичээд, «Болдын цагийг Баасан гараг руу шилжүүл» гэх мэтээр хэлнэ үү."}
              </p>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.who === "user" ? "justify-end" : ""}`}>
                <div className={`max-w-[85%] rounded-[12px] px-3.5 py-2 text-[15px] leading-6 ${m.who === "user" ? "bg-brand text-[#07130c]" : "bg-panel-2"}`}>
                  {m.text}
                </div>
              </div>
            ))}
            {busy && <div className="text-sm text-dim">AI хайж байна…</div>}
          </div>

          {showScrollBottom && (
            <button
              type="button"
              onClick={scrollToBottom}
              className="absolute bottom-16 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 rounded-full border border-line-2 bg-panel px-3 py-1.5 text-xs font-semibold shadow-md hover:border-brand cursor-pointer"
            >
              Шинэ хариулт ↓
            </button>
          )}

          <div className="flex items-end gap-2 border-t border-line px-4 py-3">
            <textarea
              ref={textareaRef}
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              disabled={busy}
              placeholder="Хэлэх зүйлээ бичнэ үү (Enter илгээх, Shift+Enter шинэ мөр)…"
              aria-label="Хэлэх зүйл"
              className="min-w-0 flex-1 resize-none overflow-y-auto rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none disabled:opacity-50"
            />
            <Button variant="primary" onClick={submit} disabled={busy || !text.trim()}>Илгээх</Button>
          </div>
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="grid gap-4 md:grid-cols-[1fr_200px]">
          <div>
            <div className="mb-2 text-[13px] text-muted">Жишээ:</div>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES[mode].map((x) => (
                <button key={x} type="button" disabled={busy} onClick={() => void send({ text: x }, x)}
                  className="cursor-pointer rounded-full border border-line-2 px-3 py-1 text-[13px] hover:border-brand disabled:opacity-40">
                  {x}
                </button>
              ))}
            </div>
            <div className="mt-4 rounded-[12px] bg-panel px-4 py-3">
              <div className="mb-2 flex items-center justify-between text-[13px] text-muted">
                <span>Бүртгэлтэй хүмүүс (код)</span>
                <span>Ажилтны код: <b className="font-mono text-fg">{staffPin}</b></span>
              </div>
              {roster.length ? (
                <ul className="space-y-1 text-sm">
                  {roster.slice(0, 8).map((p) => (
                    <li key={p.id} className="flex justify-between gap-3">
                      <span className={p.status === "canceled" ? "text-dim line-through" : ""}>{p.name || "—"} <span className="text-muted">· {p.course || "—"}</span></span>
                      <span className="font-mono text-muted">{p.code} · {LEAD_STATUS[p.status] ?? p.status}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">Бүртгэл алга.</p>
              )}
              <Button className="mt-3" onClick={samples} disabled={busy}>+ Жишээ бүртгэл (Bootcamp, эвент)</Button>
            </div>
            <div className="mt-4">
              <ReminderSim
                roster={roster}
                onResult={(r, lines) => {
                  setMsgs((x) => [...x, ...lines.map((t) => ({ who: t.startsWith("[") ? ("user" as const) : ("ai" as const), text: t }))]);
                  setPerson(r.person);
                  setChanged(new Set(r.changes.map((c) => c.field)));
                  if (r.changes.length) {
                    setChanges((x) => [...r.changes, ...x]);
                    router.refresh();
                  }
                }}
              />
            </div>
          </div>
          <div className={NEED_KEYPAD.has(state) ? "" : "opacity-50"}>
            <div className="mb-2 text-[13px] text-muted">Утасны товчлуур</div>
            <Keypad need={need || 1} disabled={busy || !NEED_KEYPAD.has(state)} onSubmit={(d) => void send({ dtmf: d }, `[товчлуур] ${state.includes("code") ? "••••" : d}`)} />
          </div>
        </div>
      </div>

      <RagPanel person={person} trace={trace} changes={changes} changed={changed} />
    </div>
  );
}