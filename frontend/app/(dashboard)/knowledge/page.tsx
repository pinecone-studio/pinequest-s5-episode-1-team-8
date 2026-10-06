import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { KnowledgeManager } from "@/components/knowledge/KnowledgeManager";
import { apiGet } from "@/lib/api";
import type { KnowledgeResponse } from "@/lib/types";

export const metadata: Metadata = { title: "Мэдээлэл (RAG)" };

export default async function KnowledgePage() {
  const data = await apiGet<KnowledgeResponse>("/api/knowledge");
  return <><PageHeader title="Мэдээлэл (RAG)" sub="Мөр бүр утсаар дангаараа уншигдах бүтэн өгүүлбэр байна. #-ээр эхэлсэн мөрийг алгасна. Засвар хийсний дараа “Аудио бэлдэх” дарна — AI сервер дахин асаахгүйгээр шинэ мэдээллийг ашиглана." /><KnowledgeManager initial={data} /></>;
}
