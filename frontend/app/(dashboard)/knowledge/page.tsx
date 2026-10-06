import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { KnowledgeManager } from "@/components/knowledge/KnowledgeManager";
import { apiGet } from "@/lib/api";
import type { KnowledgeResponse } from "@/lib/types";

export const metadata: Metadata = { title: "Мэдээлэл (RAG)" };

export default async function KnowledgePage() {
  const data = await apiGet<KnowledgeResponse>("/api/knowledge");
  return <><PageHeader title="Мэдээлэл (RAG)" sub="AI ресепшний хариулах эх сурвалж болох .md, .txt, .pdf, .docx файлууд." /><KnowledgeManager initial={data} /></>;
}
