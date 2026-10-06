import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { FaqEditor } from "@/components/faq/FaqEditor";
import { apiGet } from "@/lib/api";
import type { FaqData } from "@/lib/types";

export const metadata: Metadata = { title: "FAQ" };
export default async function FaqPage() {
  const data = await apiGet<FaqData>("/api/faq");
  return <><PageHeader title="FAQ" sub="Асуулт бүрийн хүмүүсийн асуудаг янз бүрийн хэлбэрийг олон мөрөнд бичнэ. Хариулт нь утсаар бүтнээрээ уншигдана. TODO агуулсан хариултыг алгасна." /><FaqEditor initial={data} /></>;
}
