import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { VoiceSettings } from "@/components/voice/VoiceSettings";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { ReferenceVoice, VoiceData } from "@/lib/types";

export const metadata: Metadata = { title: "Хоолой" };
export default async function VoicePage() {
  const user = await requireUser();
  const [data, reference] = await Promise.all([
    apiGet<VoiceData>("/api/voice"),
    user.role === "admin" ? apiGet<ReferenceVoice>("/api/voice/reference") : Promise.resolve(null),
  ]);
  return <><PageHeader title="Хоолой" sub="▶ сонсох, ☎ утсаар сонсогдох чанараар, ● өөрийн хоолойгоор бичих, ↻ өөр хувилбараар дахин үүсгэх. Дууссаны дараа Аудио бэлдэх дарна." /><VoiceSettings initial={data} initialReference={reference} /></>;
}
