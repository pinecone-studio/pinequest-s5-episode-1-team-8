import { Tag } from "@/components/ui/Tag";

type Tone = "ok" | "warn" | "bad" | "gray";

// AI ямар замаар хариулсан (backend db.messages.route)
const ROUTES: Record<string, [string, Tone]> = {
  greeting: ["Мэндчилгээ", "gray"], model: ["Сургасан AI", "ok"], faq: ["FAQ", "ok"], faq_near: ["FAQ (ойролцоо)", "ok"],
  fact: ["Мэдээлэл", "ok"], fact2: ["Мэдээлэл ×2", "ok"], llm: ["LLM сонголт", "ok"],
  generate: ["LLM бичсэн", "warn"], clarify: ["Тодруулсан", "warn"],
  repeat: ["Дахин асуусан", "warn"], handoff: ["Ажилтанд шилжүүлсэн", "bad"],
  en_faq: ["EN · FAQ", "ok"], en_fact: ["EN · Мэдээлэл", "ok"], en_repeat: ["EN · Дахин асуусан", "warn"],
  en_handoff: ["EN · Ажилтанд шилжүүлсэн", "bad"],
};

export function RouteTag({ route }: { route: string | null }) {
  if (route?.startsWith("lead_")) return <Tag>Бүртгэл</Tag>;
  const [label, tone] = ROUTES[route ?? ""] ?? [route || "?", "gray"];
  return <Tag tone={tone}>{label}</Tag>;
}
