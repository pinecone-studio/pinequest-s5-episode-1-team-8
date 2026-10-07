const TZ = "Asia/Ulaanbaatar";
const WEEK = ["Ням", "Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба"];

const DAY = new Intl.DateTimeFormat("en-US", { timeZone: TZ, year: "numeric", month: "numeric", day: "numeric" });

/** "Мягмар, 10-р сарын 6" хэсгүүд (Улаанбаатарын цагаар) */
export function todayParts(now = new Date()) {
  const p = Object.fromEntries(DAY.formatToParts(now).map((x) => [x.type, Number(x.value)]));
  const weekday = new Date(Date.UTC(p.year, p.month - 1, p.day)).getUTCDay();   // UB-ийн огнооны гараг
  return { weekday: WEEK[weekday], month: p.month, day: p.day };
}

// "mn-MN"-ийг Node ("X/06 12:00"), хөтөч ("10/06, 12:00 PM") өөрөөр форматалж client component-д
// hydration алдаа гаргадаг -> хэсгүүдийг нь аваад өөрсдөө угсарна (сервер, хөтөч яг ижил бичвэр)
const DATE_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: TZ, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

/** unix секунд -> "10.13 09:30" (Улаанбаатарын цагаар) */
export function formatDateTime(ts?: number | null) {
  if (!ts) return "—";
  const p = Object.fromEntries(DATE_TIME.formatToParts(new Date(ts * 1000)).map((x) => [x.type, x.value]));
  return `${p.month}.${p.day} ${p.hour}:${p.minute}`;
}

/** секунд -> "42с", "3м 05с" */
export function formatSeconds(s?: number | null) {
  if (s == null) return "—";
  const total = Math.round(s);
  return total < 60 ? `${total}с` : `${Math.floor(total / 60)}м ${String(total % 60).padStart(2, "0")}с`;
}

/** "2026-10-06" -> { day: "06", weekday: "Мяг" } */
export function dayLabel(date: string) {
  const d = new Date(`${date}T00:00:00Z`);
  return { day: date.slice(8, 10), weekday: WEEK[d.getUTCDay()].slice(0, 3) };
}
