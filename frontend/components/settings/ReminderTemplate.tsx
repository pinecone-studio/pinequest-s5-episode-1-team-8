"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import { useAction } from "@/lib/useAction";

/** AI сануулгын дуудлагын мессеж: {name} {org} {date} {time} */
export function ReminderTemplate({ initial, fallback }: { initial: string; fallback: string }) {
  const [text, setText] = useState(initial);
  const [preview, setPreview] = useState("");
  const { pending, error, message, run } = useAction();

  function save(value: string) {
    void run(async () => {
      const r = await apiSend<{ template: string; preview: string }>("/api/reminders/template", "PUT", { template: value });
      setText(r.template);
      setPreview(r.preview);
    }, "Хадгаллаа ✓");
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted">
        <code className="text-brand">{"{name}"}</code> нэр · <code className="text-brand">{"{org}"}</code> байгууллага ·{" "}
        <code className="text-brand">{"{date}"}</code> өдөр (AI үгээр уншина) · <code className="text-brand">{"{time}"}</code> цаг.
        Төгсгөлд нь «1 — баталгаажуулах, 2 — цуцлах» гэж хэлүүлнэ. Мессеж бүр ElevenLabs-аар ~150 тэмдэгт.
      </p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={600}
        className="w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg p-3 text-sm focus:border-brand focus:outline-none" />
      {preview && <p className="rounded-[10px] bg-bg px-3 py-2 text-sm"><span className="text-muted">Жишээ: </span>{preview}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={() => save(text)} disabled={pending}>Хадгалах</Button>
        <Button onClick={() => save(fallback)} disabled={pending}>Анхдагч руу</Button>
        <ActionStatus error={error} message={message} />
      </div>
    </div>
  );
}
