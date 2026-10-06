import Link from "next/link";
import { dayLabel } from "@/lib/format";
import type { Stats } from "@/lib/types";

/** Сүүлийн 5 өдрийн дуудлага: дуудлагатай өдөр ногоон зураастай */
export function CallsByDay({ days }: { days: Stats["days"] }) {
  const today = days.at(-1)?.calls ?? 0;
  return (
    <div>
      <div className="mb-[18px] flex items-baseline justify-between">
        <h2 className="text-[15px] font-semibold">Дуудлага</h2>
        <Link href="/calls" className="text-sm text-muted hover:underline">Түүх</Link>
      </div>
      <div className="mb-[18px] text-[19px] font-semibold">Өнөөдөр {today} дуудлага</div>
      <div className="flex gap-[18px]">
        {days.map((d) => {
          const { day, weekday } = dayLabel(d.date);
          return (
            <div key={d.date} className="text-center">
              <div className={`min-w-7 border-b-2 pb-1.5 font-mono text-[17px] font-medium ${d.calls ? "border-brand" : "border-line-2 text-muted"}`}>
                {day}
              </div>
              <div className="mt-2 text-xs text-muted">{weekday}</div>
              <div className="font-mono text-[11px] font-medium text-brand">{d.calls || ""}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
