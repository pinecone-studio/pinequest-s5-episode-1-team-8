import type { Stats } from "@/lib/types";

/** Хэдэн асуултад хариулсан: том тоо + хувь (зурвас) */
export function AnswerRate({ stats }: { stats: Stats }) {
  const total = stats.answered + stats.unanswered;
  const pct = total ? Math.round((100 * stats.answered) / total) : 0;
  return (
    <div>
      <h2 className="mb-[18px] text-[15px] font-semibold">Хариулт</h2>
      <div className="text-[76px] leading-none font-extrabold tracking-[-.03em] max-md:text-[56px]">
        {stats.answered}
        <small className="ml-2.5 font-mono text-[22px] font-normal tracking-normal text-muted">/ {total} асуулт</small>
      </div>
      <div
        className="mt-[26px] mb-3.5 h-1 overflow-hidden rounded-sm bg-line-2"
        role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Хариулсан хувь"
      >
        <div className="h-full rounded-sm bg-brand" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-muted">
        <b className="font-semibold text-fg">{pct}%</b>-д нь хариулсан · дундаж STT{" "}
        <b className="font-semibold text-fg">{stats.avg_stt ? `${stats.avg_stt.toFixed(1)}с` : "—"}</b>
      </p>
    </div>
  );
}
