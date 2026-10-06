import type { ReactNode } from "react";
import { todayParts } from "@/lib/format";

/** Хуудас бүрийн толгой: өнөөдрийн огноо, том гарчиг, тайлбар, баруун талд товчнууд */
export function PageHeader({ title, sub, actions, note }: { title: string; sub?: string; actions?: ReactNode; note?: ReactNode }) {
  const { weekday, month, day } = todayParts();
  return (
    <div className="mb-[34px] flex flex-wrap items-end justify-between gap-5 border-b border-line pb-[34px]">
      <div>
        <div className="mb-1 text-base text-muted">
          {weekday}, {month}-р сарын <b className="font-semibold text-fg">{day}</b>
          {note}
        </div>
        <h1 className="text-[46px] leading-[1.1] font-extrabold tracking-[-.02em] max-md:text-[34px]">{title}</h1>
        {sub && <p className="mt-2.5 max-w-[820px] text-muted">{sub}</p>}
      </div>
      {actions && <div className="flex items-center gap-[22px]">{actions}</div>}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="py-[26px] text-center text-muted">{children}</div>;
}
