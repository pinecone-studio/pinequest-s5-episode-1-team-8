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
  await requireUser();
  const [org, status, build, settings] = await Promise.all([
    apiGet<Org>("/api/org"),
    apiGet<Status>("/api/status"),
    apiGet<BuildStatus>("/api/knowledge/build"),
    apiGet<Settings>("/api/settings"),
  ]);
  const minutes = Math.max(5, Math.round(((status.facts || 40) * 6) / 60)); // өгүүлбэр бүр ~6с

  return (
    <>
      <PageHeader title="Тохируулах" sub={`${org.name} AI ресепшнийг алхам алхмаар бэлдэнэ. Код, AI мэдлэг шаардлагагүй.`} />

      <Step n={1} done={Boolean(org.phone || org.address || org.hours)} title="Байгууллагын мэдээлэл">
        <OrgForm org={org} />
      </Step>

      <Step n={2} done={org.documents > 0} title="Мэдээлэл оруулах">
        <p className="mb-3 text-muted">
          Үйлчилгээ, үнэ, нөхцөл, түгээмэл асуултын хариултаа <b className="text-fg">.docx, .pdf, .md, .txt</b> файлаар эсвэл
          шууд бичиж оруулна. Одоо: <b className="text-fg">{org.documents}</b> файл.
        </p>
        <ul className="mb-4 list-disc space-y-1 pl-5 text-muted">
          <li>Сэдэв бүрийг <code className="font-mono text-[13px] text-brand">## Гарчиг</code>-аар эхлүүлбэл AI тодруулах асуултаа гарчгаас үүсгэнэ</li>
          <li>Мөр бүр утсаар дангаараа уншигдах бүтэн өгүүлбэр байвал хамгийн сайн</li>
          <li>Тоо, утас, цагийг цифрээр бичиж болно (AI үгээр уншина)</li>
          <li>Мэдээлэлд байхгүй зүйлийг AI зохиож хэлэхгүй — ажилтан руу шилжүүлнэ</li>
        </ul>
        <Link href="/knowledge" className="inline-flex rounded-[10px] border-[1.5px] border-line-2 px-4 py-[9px] text-sm font-semibold hover:border-brand">
          Мэдээлэл оруулах →
        </Link>
      </Step>

      <Step n={3} done={status.ready && !build.running} title="Бэлдэх">
        <p className="mb-3 text-muted">
          Мэдээллээс асуултын хэлбэр, тодруулах сэдэв, FAQ-г үүсгэж, бүх хариултыг аудио болгоод AI-г сургана.
          ~{minutes}+ минут (өгүүлбэрийн тооноос хамаарна). Өөрийн бичлэгтэй өгүүлбэрт TTS хийхгүй.
        </p>
        <AutoBuildToggle initial={settings.auto_build} telegram={Boolean(settings.telegram_chat_id)} />
        <BuildPanel initial={build} />
      </Step>

      <Step n={4} done={false} title="Туршиж залгах">
        <p className="text-muted">
          Zoiper (утасны апп)-оос <b className="font-mono text-fg">{org.extension ?? "—"}</b> дугаар руу залгана. Яриа бүр{" "}
          <Link href="/calls" className="text-brand hover:underline">Яриа</Link> хэсэгт харагдана.
        </p>
        {status.selector?.eval?.selector && (
          <p className="mt-2 text-muted">
            Автомат шалгалт: <b className="text-fg">{status.selector.eval.selector[0]}/{status.selector.eval.selector[1]}</b> асуултад зөв хариулсан.
          </p>
        )}
        <p className="mt-2 text-[13px] text-muted">Эрх: {PLAN_LABEL[org.plan]}</p>
      </Step>
    </>
  );
}
