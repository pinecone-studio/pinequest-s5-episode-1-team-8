import Form from "next/form";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

const CONTROL =
  "rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2.5 text-sm text-fg placeholder:text-dim focus:border-brand focus:outline-none";

export type CallsQuery = { q: string; days: string; unanswered: boolean };

/** Яриа шүүх: дугаар/үгээр хайх, хугацаа, зөвхөн хариулж чадаагүй. URL-д хадгалагдана (?q=...&days=7) —
 *  хуваалцаж, буцаж ирэхэд хэвээр. JS-гүй ч ажиллана. */
export function CallsFilter({ value }: { value: CallsQuery }) {
  const active = Boolean(value.q || value.days || value.unanswered);
  return (
    <Form action="/calls" className="mb-[18px] flex flex-wrap items-center gap-3">
      <input
        type="search"
        name="q"
        defaultValue={value.q}
        placeholder="Дугаар эсвэл үгээр хайх (жишээ: зогсоол)"
        aria-label="Дугаар эсвэл үгээр хайх"
        maxLength={100}
        className={`${CONTROL} min-w-[240px] flex-1`}
      />
      <select name="days" defaultValue={value.days} aria-label="Хугацаа" className={CONTROL}>
        <option value="">Бүх хугацаа</option>
        <option value="1">Өнөөдөр (24 цаг)</option>
        <option value="7">Сүүлийн 7 хоног</option>
        <option value="30">Сүүлийн 30 хоног</option>
      </select>
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input type="checkbox" name="unanswered" value="true" defaultChecked={value.unanswered} className="size-4 accent-brand" />
        Зөвхөн хариулж чадаагүй
      </label>
      <Button type="submit">Шүүх</Button>
      {active && (
        <Link href="/calls" className="text-sm text-muted hover:text-fg hover:underline">Цэвэрлэх</Link>
      )}
    </Form>
  );
}
