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

  const length = text.length;

  // Өнгө болон тайлбар төлөвийг тодорхойлох
  let counterColor = "text-muted";
  let limitMessage = "";

  if (length >= 600) {
    counterColor = "text-danger font-medium";
    limitMessage = "Дээд хязгаарт хүрлээ";
  } else if (length >= 540) {
    counterColor = "text-warn font-medium";
    limitMessage = "Хязгаарт ойртлоо";
  }

  function save(value: string) {
    void run(async () => {
      const r = await apiSend<{ template: string; preview: string }>("/api/reminders/template", "PUT", { template: value });
      setText(r.template);
      setPreview(r.preview);
    }, "Хадгаллаа ✓");
  }

  // Хоосон эсвэл зөвхөн зайтай эсэхийг шалгах
  const isBlank = text.trim().length === 0;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted">
        <code className="text-brand">{"{name}"}</code> нэр · <code className="text-brand">{"{org}"}</code> байгууллага ·{" "}
        <code className="text-brand">{"{date}"}</code> өдөр (AI үгээр уншина) · <code className="text-brand">{"{time}"}</code> цаг.
        Төгсгөлд нь «1 — баталгаажуулах, 2 — цуцлах» гэж хэлүүлнэ. Мессеж бүр ElevenLabs-аар ~150 тэмдэгт.
      </p>

      <div className="relative">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          maxLength={600}
          className="w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg p-3 text-sm focus:border-brand focus:outline-none"
        />
        
        {/* Live Counter (aria-live="polite" ашигласан) */}
        <div className="mt-1.5 flex items-center justify-between text-xs" aria-live="polite">
          <span className={counterColor}>
            {limitMessage && <span className="mr-2">{limitMessage}</span>}
          </span>
          <span className={counterColor}>
            {length} / 600 тэмдэгт
          </span>
        </div>
      </div>

      {preview && <p className="rounded-[10px] bg-bg px-3 py-2 text-sm"><span className="text-muted">Жишээ: </span>{preview}</p>}
      
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={() => save(text)} disabled={pending || isBlank}>Хадгалах</Button>
        <Button onClick={() => save(fallback)} disabled={pending}>Анхдагч руу</Button>
        <ActionStatus error={error} message={message} />
      </div>
    </div>
  );
}