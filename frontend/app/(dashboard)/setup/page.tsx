import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";
import { AutoBuildToggle } from "@/components/setup/AutoBuildToggle";
import { BuildPanel } from "@/components/setup/BuildPanel";
import { OrgForm } from "@/components/setup/OrgForm";
import { Step } from "@/components/setup/Step";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import { PLAN_LABEL, type BuildStatus, type Org, type Settings, type Status } from "@/lib/types";

export const metadata: Metadata = { title: "Тохируулах" };

export default async function SetupPage() {
  const user = await requireUser();
  const [org, status, build, settings] = await Promise.all([
    apiGet<Org>("/api/org"),
    apiGet<Status>("/api/status"),
    apiGet<BuildStatus>("/api/knowledge/build"),
    apiGet<Settings>("/api/settings"),
  ]);
  const minutes = Math.max(5, Math.round(((status.facts || 40) * 6) / 60)); // өгүүлбэр бүр ~6с

  return (
    <>
      <PageHeader
        title="AI туслахаа эхлүүлэх"
        sub={user.role === "admin" ? "Доорх дөрвөн алхмыг дарааллаар нь хийнэ." : "Доорх гурван алхмыг дарааллаар нь хийнэ."}
      />

      <Step n={1} done={Boolean(org.phone || org.address || org.hours)} title="Байгууллагын мэдээлэл">
        <OrgForm org={org} />
      </Step>

      <Step n={2} done={org.documents > 0} title="Мэдээлэл оруулах">
        <p className="mb-3 text-muted">
          Үйлчилгээ, үнэ, нөхцөл болон бусад хэрэгтэй мэдээллээ файлаар эсвэл шууд бичиж оруулна.
          Одоо: <b className="text-fg">{org.documents}</b> файл.
        </p>
        <Link href="/knowledge" className="inline-flex rounded-[10px] border-[1.5px] border-line-2 px-4 py-[9px] text-sm font-semibold hover:border-brand">
          Мэдээлэл оруулах →
        </Link>
      </Step>

      <Step n={3} done={status.ready && !build.running} title="Бэлдэх">
        <p className="mb-3 text-muted">
          Оруулсан мэдээллийг AI ашиглахад бэлэн болгоно. Ойролцоогоор {minutes}+ минут үргэлжилнэ.
        </p>
        <AutoBuildToggle initial={settings.auto_build} telegram={Boolean(settings.telegram_chat_id)} />
        <BuildPanel initial={build} />
      </Step>

      {user.role === "admin" && (
        <Step n={4} done={false} title="Дотоод дугаараар турших">
          <p className="text-muted">
            Zoiper-оос <b className="font-mono text-fg">{org.extension ?? "—"}</b> дугаар руу залгана. Яриа бүр{" "}
            <Link href="/calls" className="text-brand hover:underline">Ярианууд</Link> хэсэгт харагдана.
          </p>
          {status.selector?.eval?.selector && (
            <p className="mt-2 text-muted">
              Автомат шалгалт: <b className="text-fg">{status.selector.eval.selector[0]}/{status.selector.eval.selector[1]}</b> асуултад зөв хариулсан.
            </p>
          )}
          <p className="mt-2 text-[13px] text-muted">Эрх: {PLAN_LABEL[org.plan]}</p>
        </Step>
      )}
    </>
  );
}
