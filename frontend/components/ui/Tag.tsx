import type { ReactNode } from "react";

const TONES = {
  ok: "bg-brand/12 text-brand",
  warn: "bg-warn/12 text-warn",
  bad: "bg-danger/12 text-danger",
  gray: "bg-panel-2 text-muted",
};

export function Tag({ tone = "ok", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <span className={`inline-block rounded-md px-[9px] py-0.5 font-mono text-xs font-medium whitespace-nowrap ${TONES[tone]}`}>
      {children}
    </span>
  );
}
