import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { RecordingList } from "@/components/voice/RecordingList";
import { VoiceSettings } from "@/components/voice/VoiceSettings";
import { apiGet } from "@/lib/api";
import type { VoiceData } from "@/lib/types";

export const metadata: Metadata = { title: "Хоолой" };
export default async function VoicePage() {
  const data = await apiGet<VoiceData>("/api/voice");
  return <><PageHeader title="Хоолой" sub="AI-ийн ярих хурд, завсар, үгсийн зөв дуудлага. Өгүүлбэр бүрийг өөрийн хоолойгоор бичиж эсвэл аудио файлаар оруулж болно." /><div className="space-y-6"><VoiceSettings initial={data} /><RecordingList items={data.items} /></div></>;
}
