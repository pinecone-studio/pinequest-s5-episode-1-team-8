import { Tag } from "@/components/ui/Tag";
import { formatDateTime } from "@/lib/format";
import type { DataInfo as Info } from "@/lib/types";

const kb = (b: number) => `${Math.max(1, Math.round(b / 1024))} KB`;

/** «Таны өгөгдөл»: компани өөрийн өгөгдөл хаана, юу, хэрхэн хадгалагдаж байгааг мэднэ + татах */
export function DataInfo({ info }: { info: Info }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Таны өгөгдөл</h2>
          <p className="text-sm text-muted">
            Зөвхөн танай байгууллагын тусдаа файл: <span className="font-mono text-fg">{info.location.file}</span> ({kb(info.location.bytes)})
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href="/api/database/export?format=csv" download
            className="rounded-[10px] bg-brand px-4 py-2 text-sm font-semibold text-[#07130c] hover:bg-brand-2">⬇ Бүгдийг татах (Excel/CSV)</a>
          <a href="/api/database/export?format=db" download
            className="rounded-[10px] border-[1.5px] border-line-2 px-4 py-2 text-sm font-semibold hover:border-brand">⬇ SQLite файл (.db)</a>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-[12px] bg-bg px-4 py-3">
          <h3 className="mb-2 text-sm text-muted">Юу хадгалагддаг</h3>
          <ul className="space-y-2 text-sm">
            {info.stored.map((x) => (
              <li key={x.what} className="flex justify-between gap-3">
                <span><b>{x.what}</b> <span className="text-muted">— {x.detail}</span></span>
                <span className="font-mono text-muted">{x.count}</span>
              </li>
            ))}
            {info.not_stored.map((x) => <li key={x} className="text-brand">✓ {x}</li>)}
          </ul>
        </section>
        <section className="rounded-[12px] bg-bg px-4 py-3">
          <h3 className="mb-2 text-sm text-muted">Гадагш юу явдаг</h3>
          <ul className="space-y-2 text-sm">
            {info.external.map((x) => (
              <li key={x.to}>
                <div className="flex items-center gap-2"><b>{x.to}</b>{x.active ? <Tag tone="warn">идэвхтэй</Tag> : <Tag tone="gray">тохируулаагүй</Tag>}</div>
                <div className="text-muted">{x.what}</div>
              </li>
            ))}
          </ul>
          <h3 className="mb-1 mt-3 text-sm text-muted">Энэ серверээс гарахгүй (локал AI)</h3>
          <p className="text-sm">{info.local.join(" · ")}</p>
        </section>
        <section className="rounded-[12px] bg-bg px-4 py-3 text-sm">
          <h3 className="mb-2 text-muted">Хэн харж чадах</h3>
          <ul className="mb-3 list-disc space-y-1 pl-5">{info.access.map((x) => <li key={x}>{x}</li>)}</ul>
          <h3 className="mb-1 text-muted">Хадгалах хугацаа</h3>
          <p className="mb-3">{info.retention}</p>
          <h3 className="mb-1 text-muted">Нөөцлөлт</h3>
          <p>
            {info.backup.last
              ? <>Сүүлийн нөөцлөлт: <b className="font-mono">{formatDateTime(info.backup.last)}</b> · {info.backup.count} хуулбар (сүүлийн {info.backup.keep_days} хоног)</>
              : <>Өдөр бүр автоматаар хуулбарлана (сүүлийн {info.backup.keep_days} хоног). Эхний нөөцлөлт удахгүй.</>}
          </p>
        </section>
      </div>
    </div>
  );
}
