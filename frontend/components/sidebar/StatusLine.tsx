"use client";

import type { Status } from "@/lib/types";
import { useStatus } from "@/lib/useStatus";

/** "● ОНЛАЙН  SIP ✓" — AI сервер, SIP асаалттай эсэх (10с тутам шинэчлэгдэнэ) */
export function StatusLine({ initial, isAdmin }: { initial: Status | null; isAdmin: boolean }) {
  const { status, offline } = useStatus(initial);
  const ok = "text-brand";
  const bad = "text-danger";
  return (
    <div className="flex flex-wrap gap-2.5 font-mono text-xs font-medium" role="status" aria-live="polite">
      {offline ? (
        <span className={bad}>● ВЭБ СЕРВЕР АЛГА</span>
      ) : status ? (
        <>
          <span className={status.ai_server ? ok : bad}>● {status.ai_server ? "ОНЛАЙН" : "УНТАРСАН"}</span>
          {isAdmin && <span className={status.sip ? ok : bad}>SIP {status.sip ? "✓" : "✕"}</span>}
        </>
      ) : null}
    </div>
  );
}
