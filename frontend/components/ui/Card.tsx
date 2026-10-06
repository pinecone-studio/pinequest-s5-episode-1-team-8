import type { ReactNode } from "react";

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`min-w-0 rounded-[14px] bg-panel px-[22px] py-5 ${className}`}>{children}</div>;
}

/** Самбарын тоон карт: жижиг шошго + том утга */
export function StatCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Card>
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-[26px] font-extrabold tracking-[-.02em] break-words">{children}</div>
    </Card>
  );
}
