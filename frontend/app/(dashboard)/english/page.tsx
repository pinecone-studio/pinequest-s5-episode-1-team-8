import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { EnglishEditor } from "@/components/english/EnglishEditor";
import { apiGet } from "@/lib/api";
import type { EnglishData } from "@/lib/types";

export const metadata: Metadata = { title: "Англи хэл" };
export default async function EnglishPage() {
  const data = await apiGet<EnglishData>("/api/english");
  return <><PageHeader title="Англи хэл" sub="Монгол хариултын баталгаатай англи орчуулга болон англи асуултын хувилбарууд." /><EnglishEditor initial={data} /></>;
}
