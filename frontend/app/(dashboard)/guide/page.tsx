import type { Metadata } from "next";
import Link from "next/link";
import { FAQS, HOWTOS, QUICKSTART, SECTIONS } from "@/components/guide/content";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { requireUser } from "@/lib/session";

export const metadata: Metadata = { title: "Заавар" };

export default async function GuidePage() {
  await requireUser();
  return (
    <>
      <PageHeader
        title="Заавар"
        sub="AI ресепшнийг хэрхэн ашиглах вэ: эхлэх алхмууд, цэс бүр юунд зориулагдсан, түгээмэл нөхцөлд юу хийх, байнга асуудаг асуултууд."
      />

      <Section title="Хурдан эхлэх — 5 алхам">
        <ol className="grid gap-3 md:grid-cols-5">
          {QUICKSTART.map((s, i) => (
            <li key={s.title}>
              <Link href={s.href} className="block h-full rounded-[14px] bg-panel px-5 py-4 hover:bg-panel-2">
                <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-full bg-brand font-bold text-[#07130c]">{i + 1}</div>
                <div className="mb-1 font-semibold">{s.title}</div>
                <p className="text-sm leading-5 text-muted">{s.text}</p>
              </Link>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Хэрхэн хийх вэ">
        <div className="space-y-2">
          {HOWTOS.map((h) => (
            <details key={h.title} className="group rounded-[14px] bg-panel px-5 py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                <span className="font-semibold">{h.title}</span>
                <span className="flex items-center gap-3 text-[13px] text-muted">
                  <span className="max-md:hidden">{h.who}</span>
                  <span className="transition-transform group-open:rotate-90">›</span>
                </span>
              </summary>
              <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-[15px] leading-6">
                {h.steps.map((s) => <li key={s}>{s}</li>)}
              </ol>
              <div className="mt-3 flex flex-wrap gap-3 text-sm">
                {h.links.map((l) => <Link key={l.href + l.label} href={l.href} className="text-brand hover:underline">{l.label} →</Link>)}
              </div>
            </details>
          ))}
        </div>
      </Section>

      {SECTIONS.map((g) => (
        <Section key={g.group} title={`Цэс: ${g.group}`}>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {g.items.map((s) => (
              <Card key={s.href}>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-lg font-semibold">{s.icon} {s.title}</span>
                  <Link href={s.href} className="text-sm text-brand hover:underline">Нээх →</Link>
                </div>
                <p className="mb-2 text-sm text-muted">{s.what}</p>
                <ul className="list-disc space-y-1 pl-5 text-sm">{s.how.map((x) => <li key={x}>{x}</li>)}</ul>
              </Card>
            ))}
          </div>
        </Section>
      ))}

      <Section title="Байнга асуудаг асуултууд">
        <div className="space-y-2">
          {FAQS.map((f) => (
            <details key={f.q} className="rounded-[14px] bg-panel px-5 py-4">
              <summary className="cursor-pointer font-semibold">{f.q}</summary>
              <p className="mt-2 text-[15px] leading-6 text-muted">{f.a}</p>
            </details>
          ))}
        </div>
      </Section>
    </>
  );
}
