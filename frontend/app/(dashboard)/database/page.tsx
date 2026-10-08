import type { Metadata } from "next";
import Link from "next/link";
import { DataInfo } from "@/components/database/DataInfo";
import { DbTableView } from "@/components/database/DbTableView";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { requireAdmin } from "@/lib/session";
import type { DataInfo as Info, DbOverview, DbRows } from "@/lib/types";

export const metadata: Metadata = { title: "Өгөгдлийн сан" };

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export default async function DatabasePage({ searchParams }: PageProps<"/database">) {
  await requireAdmin();
  const sp = await searchParams;
  const [db, info] = await Promise.all([apiGet<DbOverview>("/api/database"), apiGet<Info>("/api/database/info")]);
  const table = db.tables.some((x) => x.name === one(sp.table)) ? one(sp.table) : db.tables[0]?.name;
  const q = one(sp.q).trim().slice(0, 100);
  const offset = Math.max(0, Number.parseInt(one(sp.offset), 10) || 0);
  const rows = table
    ? await apiGet<DbRows>(`/api/database/${encodeURIComponent(table)}?${new URLSearchParams({ q, offset: String(offset) })}`)
    : null;

  return (
    <>
      <PageHeader
        title="Өгөгдлийн сан"
        sub="Байгууллагын бүртгэл, дуудлага болон мэдлэгийн сангийн мэдээллийг хүснэгтээр харах."
      />
      <Card className="mb-5">
        <DataInfo info={info} />
      </Card>
      <div className="space-y-4">
        <nav aria-label="Өгөгдлийн сангийн хүснэгтүүд" className="flex flex-wrap justify-center gap-2">
          {db.tables.map((x) => (
            <Link
              key={x.name}
              href={`/database?table=${x.name}`}
              aria-current={x.name === table ? "page" : undefined}
              className={`inline-flex min-w-[140px] items-center justify-center gap-2 rounded-[10px] border px-4 py-2.5 transition-colors ${x.name === table ? "border-brand bg-panel-2 text-fg" : "border-line bg-panel text-muted hover:border-line-2 hover:bg-panel-2 hover:text-fg"}`}
            >
              <span className="font-mono text-sm font-semibold">{x.name}</span>
              <span className={`font-mono text-xs ${x.name === table ? "text-brand" : "text-muted"}`}>{x.rows}</span>
            </Link>
          ))}
        </nav>
        <Card>
          {rows ? (
            <>
              <h2 className="mb-1 font-mono text-lg font-semibold">{rows.table}</h2>
              {rows.about && <p className="mb-1 text-sm text-muted">{rows.about}</p>}
              <p className="mb-4 text-xs text-dim">{rows.columns.length} багана · {rows.total} мөр</p>
              <DbTableView data={rows} q={q} />
            </>
          ) : (
            <p className="text-muted">Хүснэгт алга.</p>
          )}
        </Card>
      </div>
    </>
  );
}
