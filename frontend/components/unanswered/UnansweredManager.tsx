"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { RouteTag } from "@/components/calls/RouteTag";
import { EmptyState } from "@/components/PageHeader";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type {
  JobStatus,
  TrainingAnswers,
  UnansweredReview,
  UnansweredReviewItem,
  UnansweredSuggestion,
} from "@/lib/types";

const FAIL_ROUTES = new Set(["repeat", "handoff", "en_repeat", "en_handoff"]);

export function UnansweredManager({ initial, answers }: { initial: UnansweredReview; answers: TrainingAnswers | null }) {
  const [items, setItems] = useState(initial.items);
  const [pendingNotes, setPendingNotes] = useState(initial.pending);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const groups = useMemo(() => {
    const noise = items.filter((item) => item.now?.noise);
    const solved = items.filter((item) => item.now && !item.now.noise && !FAIL_ROUTES.has(item.now.route ?? ""));
    const excluded = new Set([...noise, ...solved]);
    return { noise, solved, todo: items.filter((item) => !excluded.has(item)) };
  }, [items]);

  async function action(key: string, fn: () => Promise<void>, ok: string) {
    setBusy(key); setError(""); setMessage("");
    try {
      await fn();
      setMessage(ok);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function hide(question: string) {
    await action(`hide:${question}`, async () => {
      await apiSend("/api/unanswered/hide", "POST", { q: question });
      setItems((all) => all.filter((item) => item.q !== question));
    }, "Жагсаалтаас нуусан ✓");
  }

  async function hideAll(list: UnansweredReviewItem[], kind: string) {
    await action(`hide-all:${kind}`, async () => {
      await Promise.all(list.map((item) => apiSend("/api/unanswered/hide", "POST", { q: item.q })));
      const removed = new Set(list.map((item) => item.q));
      setItems((all) => all.filter((item) => !removed.has(item.q)));
    }, "Сонгосон асуултуудыг нуусан ✓");
  }

  async function teach(item: UnansweredReviewItem, answer: string) {
    if (!answer) return setError("Зөв хариултыг сонгоно уу");
    await action(`teach:${item.q}`, async () => {
      await apiSend("/api/unanswered/teach", "POST", { q: item.q, answer });
      setItems((all) => all.filter((row) => row.q !== item.q));
      setPendingNotes((all) => [...all, `заасан: ${item.q}`]);
    }, "Зөв хариултыг заалаа ✓");
  }

  async function saveAnswer(item: UnansweredReviewItem, answer: string, questions: string[]) {
    await action(`answer:${item.q}`, async () => {
      await apiSend("/api/unanswered/answer", "POST", { q: item.q, answer, questions });
      setItems((all) => all.filter((row) => row.q !== item.q));
      setPendingNotes((all) => [...all, `шинэ хариулт: ${answer.slice(0, 60)}`]);
    }, "Шинэ хариултыг хадгаллаа ✓");
  }

  async function apply() {
    if (!window.confirm("Шинэ хариултын аудио үүсгэж AI-г сургах уу?")) return;
    await action("apply", async () => {
      await apiSend<JobStatus>("/api/unanswered/apply", "POST");
      setPendingNotes([]);
    }, "Аудио болон сургалт дараалалд орлоо ✓");
  }

  return (
    <div className="space-y-7">
      {!initial.live && items.length > 0 && (
        <div className="rounded-[12px] border border-warn/35 bg-warn/10 px-4 py-3 text-sm text-warn">
          AI review сервер унтарсан тул одоогийн хариултыг дахин шалгаж чадсангүй. Хариулт заах болон шинээр бичих боломж хэвийн ажиллана.
        </div>
      )}

      {pendingNotes.length > 0 && (
        <Card className="flex flex-wrap items-center gap-4 border border-brand/25">
          <div className="min-w-[240px] flex-1">
            <b>{pendingNotes.length} өөрчлөлт</b> хэрэгжүүлэхэд бэлэн
            <p className="mt-1 text-sm text-muted">{pendingNotes.slice(-3).join(" · ")}{pendingNotes.length > 3 ? " …" : ""}</p>
          </div>
          <Button variant="primary" onClick={() => void apply()} disabled={Boolean(busy)}>
            {busy === "apply" ? "Дараалалд оруулж байна…" : "Хэрэгжүүлэх · аудио + сургалт"}
          </Button>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Шийдэх шаардлагатай">{groups.todo.length}</StatCard>
        <StatCard label="Одоо хариулдаг болсон">{groups.solved.length}</StatCard>
        <StatCard label="Чимээ / гацсан STT">{groups.noise.length}</StatCard>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Шийдэх шаардлагатай</h2>
        {groups.todo.length ? groups.todo.map((item) => (
          <QuestionCard key={item.q} item={item} answers={answers} busy={busy}
            onHide={hide} onTeach={teach} onSave={saveAnswer} />
        )) : <Card><EmptyState>Бүгд шийдэгдсэн 🎉</EmptyState></Card>}
      </section>

      {groups.solved.length > 0 && (
        <ReviewGroup title="Одоо хариулдаг болсон" items={groups.solved} busy={busy}
          onHide={hide} onHideAll={() => void hideAll(groups.solved, "solved")} />
      )}
      {groups.noise.length > 0 && (
        <ReviewGroup title="Чимээ / гацсан яриа таних" items={groups.noise} busy={busy}
          onHide={hide} onHideAll={() => void hideAll(groups.noise, "noise")} />
      )}
      <ActionStatus error={error} message={message} />
    </div>
  );
}

function QuestionCard({ item, answers, busy, onHide, onTeach, onSave }: {
  item: UnansweredReviewItem;
  answers: TrainingAnswers | null;
  busy: string;
  onHide: (question: string) => Promise<void>;
  onTeach: (item: UnansweredReviewItem, answer: string) => Promise<void>;
  onSave: (item: UnansweredReviewItem, answer: string, questions: string[]) => Promise<void>;
}) {
  const [selected, setSelected] = useState("");
  const [answer, setAnswer] = useState("");
  const [questions, setQuestions] = useState("");
  const suggestions = (item.now?.suggest ?? []).filter((suggestion) => suggestion.value);
  const disabled = Boolean(busy);
  const choices = answers ? [["Тусгай", answers.special], ["FAQ", answers.faq], ["Мэдээлэл", answers.facts]] as const : [];

  return (
    <Card>
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{item.q}</p>
          {item.now?.fixed && item.now.fixed !== item.q && <p className="mt-1 text-sm text-muted">STT засвар: {item.now.fixed}</p>}
          <p className="mt-1 text-sm text-muted">
            {formatDateTime(item.ts)} · <Link className="text-brand hover:underline" href={`/calls/${item.call_uuid}`}>Дуудлага харах</Link>
          </p>
        </div>
        <Button aria-label="Нуух" title="Жагсаалтаас нуух" onClick={() => void onHide(item.q)} disabled={disabled}>×</Button>
      </div>

      {item.now?.route && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-muted">
          <span>Одоо AI:</span><RouteTag route={item.now.route} />
          {item.now.reply && <span>{item.now.reply.slice(0, 160)}</span>}
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="mt-5 space-y-2">
          <p className="text-sm text-muted">Мэдээллээс санал болгосон хариулт</p>
          {suggestions.map((suggestion) => (
            <Suggestion key={`${suggestion.value}:${suggestion.text}`} suggestion={suggestion} disabled={disabled}
              onChoose={() => void onTeach(item, suggestion.value)} />
          ))}
        </div>
      )}

      <details className="mt-5 rounded-[10px] border border-line-2 px-4 py-3 open:bg-bg/35">
        <summary className="cursor-pointer font-medium">Өөр хариулт сонгох эсвэл шинээр бичих</summary>
        <div className="mt-4 flex flex-wrap gap-2">
          <select value={selected} onChange={(event) => setSelected(event.target.value)}
            className="min-w-[260px] flex-1 rounded-[10px] border border-line-2 bg-bg px-3 py-2.5">
            <option value="">— байгаа хариултаас —</option>
            {choices.map(([label, list]) => list.length > 0 && <optgroup key={label} label={label}>
              {list.map((choice) => <option key={choice.value} value={choice.value}>{choice.title}</option>)}
            </optgroup>)}
          </select>
          <Button onClick={() => void onTeach(item, selected)} disabled={disabled || !selected}>Заах</Button>
        </div>

        <label className="mt-5 block text-sm text-muted">Шинэ хариулт</label>
        <textarea value={answer} onChange={(event) => setAnswer(event.target.value)} rows={3} maxLength={400}
          placeholder="Байгууллагын баталгаатай хариултыг бичнэ үү"
          className="mt-2 w-full resize-y rounded-[10px] border border-line-2 bg-bg px-3 py-2.5 focus:border-brand focus:outline-none" />
        <label className="mt-4 block text-sm text-muted">Ижил утгатай өөр асуултууд · мөр бүрд нэг</label>
        <textarea value={questions} onChange={(event) => setQuestions(event.target.value)} rows={2}
          placeholder={item.now?.fixed || item.q}
          className="mt-2 w-full resize-y rounded-[10px] border border-line-2 bg-bg px-3 py-2.5 focus:border-brand focus:outline-none" />
        <div className="mt-3 flex justify-end">
          <Button variant="primary" disabled={disabled || answer.trim().length < 5}
            onClick={() => void onSave(item, answer.trim(), questions.split("\n").map((value) => value.trim()).filter(Boolean))}>
            Хариулт хадгалах
          </Button>
        </div>
      </details>
    </Card>
  );
}

function Suggestion({ suggestion, disabled, onChoose }: { suggestion: UnansweredSuggestion; disabled: boolean; onChoose: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-[10px] bg-bg/55 px-3 py-2.5">
      <span className="min-w-[220px] flex-1 text-sm">{suggestion.text}</span>
      <span className="font-mono text-xs text-muted">{Math.round(suggestion.score * 100)}%</span>
      <Button onClick={onChoose} disabled={disabled}>Энэ зөв</Button>
    </div>
  );
}

function ReviewGroup({ title, items, busy, onHide, onHideAll }: {
  title: string;
  items: UnansweredReviewItem[];
  busy: string;
  onHide: (question: string) => Promise<void>;
  onHideAll: () => void;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Button onClick={onHideAll} disabled={Boolean(busy)}>Бүгдийг нуух</Button>
      </div>
      <Card className="divide-y divide-line">
        {items.map((item) => (
          <div key={item.q} className="flex items-start gap-4 py-3 first:pt-0 last:pb-0">
            <div className="min-w-0 flex-1">
              <p className={item.now?.noise ? "text-muted" : ""}>{item.q}</p>
              {item.now?.fixed && item.now.fixed !== item.q && <p className="mt-1 text-sm text-muted">STT засвар: {item.now.fixed}</p>}
              {!item.now?.noise && item.now?.route && <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
                <RouteTag route={item.now.route} />{item.now.reply?.slice(0, 140)}
              </div>}
            </div>
            <Button aria-label="Нуух" onClick={() => void onHide(item.q)} disabled={Boolean(busy)}>×</Button>
          </div>
        ))}
      </Card>
    </section>
  );
}
