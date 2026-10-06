import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";
import { OrgForm } from "@/components/setup/OrgForm";
import { Step } from "@/components/setup/Step";
import { Button } from "@/components/ui/Button";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import { PLAN_LABEL, type Org } from "@/lib/types";

export const metadata: Metadata = { title: "Тохируулах" };

export default async function SetupPage() {
  await requireUser();
  const org = await apiGet<Org>("/api/org");

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

      <Step n={3} done={false} title="Бэлдэх">
        <p className="mb-3 text-muted">
          Мэдээллээс асуултын хэлбэр, FAQ-г үүсгэж, бүх хариултыг аудио болгоод AI-г сургана.
        </p>
        <Button disabled title="AI хэсэг нэмэгдсэний дараа">Бэлдэх (удахгүй)</Button>
      </Step>

      <Step n={4} done={false} title="Туршиж залгах">
        <p className="text-muted">
          Zoiper (утасны апп)-оос <b className="font-mono text-fg">{org.extension ?? "—"}</b> дугаар руу залгана. Яриа бүр{" "}
          <Link href="/calls" className="text-brand hover:underline">Яриа</Link> хэсэгт харагдана.
        </p>
        <p className="mt-2 text-[13px] text-muted">Эрх: {PLAN_LABEL[org.plan]}</p>
      </Step>
    </>
  );
}
