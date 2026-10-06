import type { ReactNode } from "react";

/** Хуудасны хэсэг: гарчиг (баруун талд холбоос/таг), доор нь агуулга, хооронд зураас */
export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="mb-[34px] border-b border-line pb-[34px] last:border-b-0">
      <div className="mb-[18px] flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[15px] font-semibold">{title}</h2>
        {aside && <div className="text-sm text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  );
}
