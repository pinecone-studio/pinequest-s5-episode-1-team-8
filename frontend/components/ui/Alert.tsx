import type { ReactNode } from "react";

/** Алдааны мессеж (дэлгэц уншигч шууд уншина) */
export function Alert({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-[10px] bg-danger/12 px-3 py-2.5 text-sm text-danger">
      {children}
    </p>
  );
}
