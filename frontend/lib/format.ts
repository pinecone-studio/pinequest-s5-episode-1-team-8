const TZ = "Asia/Ulaanbaatar";
const WEEK = ["Ням", "Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба"];

/** "Мягмар, 10-р сарын 6" хэсгүүд (Улаанбаатарын цагаар) */
export function todayParts(now = new Date()) {
  const ub = new Date(now.toLocaleString("en-US", { timeZone: TZ }));
  return { weekday: WEEK[ub.getDay()], month: ub.getMonth() + 1, day: ub.getDate() };
}

/** unix секунд -> "10.13 09:30" */
export function formatDateTime(ts?: number | null) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("mn-MN", {
    timeZone: TZ, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

/** секунд -> "42с", "3м 05с" */
export function formatSeconds(s?: number | null) {
  if (s == null) return "—";
  const total = Math.round(s);
  return total < 60 ? `${total}с` : `${Math.floor(total / 60)}м ${String(total % 60).padStart(2, "0")}с`;
}
