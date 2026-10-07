"use client";

import { useState, type FormEvent } from "react";
import { BuildPanel } from "@/components/knowledge/BuildPanel";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { TrainingAnswers, TrainingStatus } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function TrainingManager({ initial, answers }: { initial: TrainingStatus; answers: TrainingAnswers }) {
  const [rows, setRows] = useState(initial.taught);
  const { pending, error, message, run } = useAction();
  const model = initial.model;
  const evaluation = model?.eval;
  const choices = [["FAQ", answers.faq], ["Мэдээлэл", answers.facts], ["Тусгай", answers.special]] as const;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    void run(async () => {
      await apiSend("/api/train/examples", "POST", { q: data.get("q"), answer: data.get("answer") });
      form.reset(); const next = await apiSend<TrainingStatus>("/api/train", "GET"); setRows(next.taught);
    }, "Сургалтын жишээ нэмэгдлээ ✓");
  }

  return (
    <div className="space-y-7">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat value={model ? model.enabled ? "Идэвхтэй" : "Идэвхгүй" : "—"}
          label={model ? model.enabled ? "Дуудлагад ашиглаж байна" : "Дүрмээс муу тул ашиглахгүй" : "Сургаагүй"} />
        <Stat value={evaluation ? `${evaluation.selector[0]}/${evaluation.selector[1]}` : "—"}
          label={`Шалгалт (сургасан AI)${evaluation ? ` · дүрэм ${evaluation.rules[0]}/${evaluation.rules[1]}` : ""}`} />
        <Stat value={model?.examples ?? "—"} label={`Жишээ · ${rows.length} нь бодит дуудлагаас`} />
        <Stat value={model?.answers ?? model?.labels?.length ?? "—"} label={`Хариулт · сүүлд ${formatDateTime(model?.trained_at)}`} />
      </div>

      <BuildPanel startPath="/api/train" statusPath="/api/train" title="Сургалтын лог" buttonLabel="Сургах"
        description={`~1–3 минут. Сургасны дараа сургалтад ороогүй шалгалтын асуултуудаар хэмжиж, дүрмээс муу бол автоматаар идэвхгүй болгоно. Мэдээллээс автоматаар ${initial.auto} асуулт үүсгэсэн. AI сервер шинэ загварыг дараагийн дуудлага дээр ачаална.`} />

      <form onSubmit={submit} className="rounded-[14px] bg-panel px-[22px] py-5">
        <h2 className="mb-4 font-semibold">Зөв хариулт заах</h2>
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]"><input name="q" required placeholder="Залгагчийн бодит асуулт" className="rounded-[10px] border border-line-2 bg-bg px-3 py-2.5" />
          <select name="answer" required defaultValue="" className="rounded-[10px] border border-line-2 bg-bg px-3 py-2.5"><option value="" disabled>— зөв хариулт —</option>{choices.map(([label, list]) => <optgroup key={label} label={label}>{list.map((choice) => <option key={choice.value} value={choice.value}>{choice.title}</option>)}</optgroup>)}</select>
          <Button variant="primary" disabled={pending}>Нэмэх</Button></div>
      </form>

      <section className="rounded-[14px] bg-panel px-[22px] py-5"><h2 className="mb-3 font-semibold">Бодит дуудлагаас заасан жишээ</h2>
        {rows.length ? <div className="divide-y divide-line">{rows.map((row) => <div key={row.i} className="grid items-center gap-3 py-3 md:grid-cols-[1fr_1fr_auto]">
          <p>{row.q}</p><span className="text-sm text-muted">{row.faq ? `FAQ: ${row.faq}` : row.fact ? row.fact.slice(0, 120) : row.label === "other" ? "Мэдээлэлд алга" : "Тодруулна"}</span>
          <Button className="text-danger" onClick={() => void run(async () => { await apiSend(`/api/train/examples/${row.i}`, "DELETE"); setRows((all) => all.filter((item) => item.i !== row.i)); }, "Жишээ устлаа")}>Устгах</Button>
        </div>)}</div> : <p className="py-8 text-center text-muted">Одоохондоо алга. Хариулж чадаагүй асуултын зөв хариултыг заагаарай.</p>}
      </section>
      <ActionStatus error={error} message={message} />
    </div>
  );
}

function Stat({ value, label }: { value: number | string; label: string }) {
  return <div className="rounded-[14px] bg-panel px-[22px] py-7"><div className="text-[34px] font-extrabold tracking-[-.02em]">{value}</div><div className="mt-2 text-sm leading-6 text-muted">{label}</div></div>;
}
