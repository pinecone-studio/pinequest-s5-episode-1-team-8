"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { WeeklyReport as Report } from "@/lib/types";
import { useAction } from "@/lib/useAction";

/** Долоо хоногийн тайлан: Даваа бүр 09:00-д Telegram руу (асаах/унтраах, урьдчилан харах, одоо илгээх) */
export function WeeklyReport({ initial }: { initial: Report }) {
  const [enabled, setEnabled] = useState(initial.enabled);
  const { pending, error, message, run } = useAction();

  function toggle(next: boolean) {
    setEnabled(next);
    void run(() => apiSend("/api/report/settings", "PUT", { enabled: next }), next ? "Асаалаа ✓" : "Унтраалаа");
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="flex cursor-pointer items-center gap-2.5 text-sm font-semibold">
        <input type="checkbox" className="size-4 accent-brand" checked={enabled} onChange={(e) => toggle(e.target.checked)} />
        Даваа бүр 09:00-д Telegram руу илгээх
      </label>
      {!initial.telegram && <p className="text-sm text-muted">Эхлээд дээрх Telegram мэдэгдлийг тохируулна уу.</p>}
      <pre className="rounded-[10px] bg-bg px-4 py-3 font-sans text-sm leading-6 whitespace-pre-wrap">{initial.text}</pre>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void run(() => apiSend("/api/report/send", "POST"), "Илгээлээ ✓ Telegram-аа шалгана уу")}
          disabled={pending || !initial.telegram}>Одоо илгээх</Button>
        {initial.last_sent ? <span className="text-sm text-muted">Сүүлд илгээсэн: {formatDateTime(initial.last_sent)}</span> : null}
        <ActionStatus error={error} message={message} />
      </div>
    </div>
  );
}
