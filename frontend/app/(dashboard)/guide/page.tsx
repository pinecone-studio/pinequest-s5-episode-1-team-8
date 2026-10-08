import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { requireUser } from "@/lib/session";

export const metadata: Metadata = { title: "Тусламж" };

const START = [
  { href: "/setup", title: "1. Байгууллагаа оруулах", text: "Нэр, утас, хаяг, ажиллах цагаа бөглөнө." },
  { href: "/knowledge", title: "2. AI-д мэдээлэл өгөх", text: "Үйлчилгээ, үнэ болон нөхцөлөө оруулна." },
  { href: "/faq", title: "3. Асуулт, хариултаа шалгах", text: "Түгээмэл асуултын хариултыг засна." },
  { href: "/calls", title: "4. Дуудлагаа хянах", text: "Дугаарын холболтыг манай баг хийнэ. Орж ирсэн яриаг эндээс шалгана." },
];

const DAILY = [
  { href: "/unanswered", title: "Хариулаагүй асуулт", text: "AI мэдээгүй асуултад зөв хариулт нэмнэ." },
  { href: "/leads", title: "Бүртгэлүүд", text: "Холбогдох шаардлагатай хүмүүсийн төлөв, тэмдэглэлийг хөтөлнө." },
  { href: "/settings", title: "Мэдэгдэл ба тохиргоо", text: "Telegram мэдэгдэл, тайлан болон нууц үгээ тохируулна." },
];

const ADMIN = [
  { href: "/admin", title: "Байгууллагууд", text: "Байгууллага нэмэх, эрх болон төлөвийг удирдах." },
  { href: "/assistant", title: "AI туршилт", text: "Утасгүйгээр AI-ийн ажиллагааг шалгах." },
  { href: "/train", title: "AI сургалт", text: "Хариулт сонголтын сургалт, үнэлгээг ажиллуулах." },
  { href: "/database", title: "Өгөгдлийн сан", text: "Хүснэгт болон системийн өгөгдлийг шалгах." },
];

export default async function GuidePage() {
  const user = await requireUser();
  return (
    <>
      <PageHeader title="Тусламж" sub="AI туслахаа эхлүүлэх болон өдөр тутам ашиглах товч заавар." />

      <LinkCards title="Эхлүүлэх 4 алхам" items={START} columns="md:grid-cols-2 xl:grid-cols-4" />
      <LinkCards title="Өдөр тутам хийх зүйл" items={DAILY} columns="md:grid-cols-3" />

      {user.role === "admin" && (
        <LinkCards title="Admin хэрэгслүүд" items={ADMIN} columns="md:grid-cols-2 xl:grid-cols-4" />
      )}

      <Section title="Түгээмэл асуулт">
        <div className="space-y-2">
          <HelpItem question="AI байхгүй мэдээлэл зохиож хэлэх үү?">
            Үгүй. AI зөвхөн таны оруулсан мэдээлэл болон бэлэн хариултаас сонгоно.
          </HelpItem>
          <HelpItem question="Мэдээлэл өөрчилсний дараа яах вэ?">
            Эхлүүлэх хуудасны бэлдэх үйлдлийг ажиллуулна. Автомат бэлдэх асаалттай бол өөрөө шинэчлэгдэнэ.
          </HelpItem>
          <HelpItem question="Залгагчийн дуу бичигдэх үү?">
            Үгүй. Зөвхөн ярианы бичвэр хадгалагдана.
          </HelpItem>
        </div>
      </Section>
    </>
  );
}

function LinkCards({ title, items, columns }: {
  title: string;
  items: { href: string; title: string; text: string }[];
  columns: string;
}) {
  return (
    <Section title={title}>
      <div className={`grid gap-3 ${columns}`}>
        {items.map((item) => (
          <Link key={item.href} href={item.href} className="block rounded-[14px] bg-panel px-5 py-4 hover:bg-panel-2">
            <h2 className="mb-1 font-semibold">{item.title}</h2>
            <p className="text-sm leading-5 text-muted">{item.text}</p>
          </Link>
        ))}
      </div>
    </Section>
  );
}

function HelpItem({ question, children }: { question: string; children: ReactNode }) {
  return (
    <Card>
      <h2 className="mb-1 font-semibold">{question}</h2>
      <p className="text-sm text-muted">{children}</p>
    </Card>
  );
}
