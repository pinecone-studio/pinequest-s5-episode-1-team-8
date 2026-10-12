import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { FaqEditor } from "@/components/faq/FaqEditor";
import { apiGet } from "@/lib/api";
import type { FaqData } from "@/lib/types";

export const metadata: Metadata = { title: "Асуулт, хариулт" };
export default async function FaqPage() {
  const data = await apiGet<FaqData>("/api/faq");
  return <><PageHeader title="Асуулт, хариулт" sub="Залгагчдын түгээмэл асуулт болон AI туслахын хэлэх хариултыг засна." /><FaqEditor initial={data} /></>;
}
