import type { Metadata } from "next";
import Link from "next/link";
import { DataInfo } from "@/components/database/DataInfo";
import { DbTableView } from "@/components/database/DbTableView";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { DataInfo as Info, DbOverview, DbRows } from "@/lib/types";

export const metadata: Metadata = { title: "Өгөгдлийн сан" };

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export default async function DatabasePage({ searchParams }: PageProps<"/database">) {
  await requireUser();
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
        sub={`Байгууллагын бүх өгөгдөл нэг SQLite файлд: ${db.file} (${Math.max(1, Math.round(db.bytes / 1024))} KB). Байгууллагын RAG, хүн бүрийн хувийн RAG (вектортой), бүртгэл, өөрчлөлт, дуудлага. Зөвхөн харах — өөрчлөлтийг AI туслах, сануулгын дуудлага хийнэ.`}
      />
      <Card className="mb-5">
        <DataInfo info={info} />
      </Card>
      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <nav className="space-y-2">
          {db.tables.map((x) => (
            <Link
              key={x.name}
              href={`/database?table=${x.name}`}
              className={`block rounded-[12px] px-4 py-3 ${x.name === table ? "bg-panel-2 ring-[1.5px] ring-brand" : "bg-panel hover:bg-panel-2"}`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-sm font-semibold">{x.name}</span>
                <span className="font-mono text-[13px] text-muted">{x.rows}</span>
              </div>
              {x.about && <div className="mt-0.5 text-[13px] text-muted">{x.about}</div>}
            </Link>
          ))}
        </nav>
        <Card>
          {rows ? (
            <>
              <h2 className="mb-1 font-mono text-lg font-semibold">{rows.table}</h2>
              {rows.about && <p className="mb-4 text-sm text-muted">{rows.about}</p>}
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
