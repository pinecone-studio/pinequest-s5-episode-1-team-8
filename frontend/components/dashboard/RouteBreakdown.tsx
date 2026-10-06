import type { Stats } from "@/lib/types";

/** AI ямар замаар хариулсан (backend-ийн route-уудыг бүлэглэнэ) */
export function RouteBreakdown({ routes }: { routes: Stats["routes"] }) {
  const r = (...keys: string[]) => keys.reduce((sum, k) => sum + (routes[k] ?? 0), 0);
  const ways: [string, number][] = [
    ["Сургасан AI", r("model")],
    ["FAQ", r("faq", "faq_near", "en_faq")],
    ["Мэдээлэл (RAG)", r("fact", "fact2", "llm", "en_fact")],
    ["Тодруулж асуусан", r("clarify")],
    ["Дахин асуусан", r("repeat", "en_repeat")],
    ["Ажилтанд шилжүүлсэн", r("handoff", "en_handoff")],
  ];
  return (
    <div>
      <h2 className="mb-[18px] text-[15px] font-semibold">Хариултын зам</h2>
      <ul>
        {ways.map(([label, n]) => (
          <li key={label} className="flex justify-between gap-4 py-1.5 text-lg">
            <span>{label}</span>
            <span className="font-mono text-base text-muted">{n}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
