import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { KnowledgeManager } from "@/components/knowledge/KnowledgeManager";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { KnowledgeResponse } from "@/lib/types";

export const metadata: Metadata = { title: "AI-ийн мэдээлэл" };

export default async function KnowledgePage() {
  const user = await requireUser();
  const data = await apiGet<KnowledgeResponse>("/api/knowledge");
  return <><PageHeader title="AI-ийн мэдээлэл" sub="AI туслахын хэлэх үйлчилгээ, үнэ, цагийн хуваарь болон бусад мэдээллийг энд оруулна." /><KnowledgeManager initial={data} isAdmin={user.role === "admin"} /></>;
}
