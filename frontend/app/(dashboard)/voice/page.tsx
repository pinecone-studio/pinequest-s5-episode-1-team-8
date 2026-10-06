import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { VoiceSettings } from "@/components/voice/VoiceSettings";
import { apiGet } from "@/lib/api";
import type { VoiceData } from "@/lib/types";

export const metadata: Metadata = { title: "Хоолой" };
export default async function VoicePage() {
  const data = await apiGet<VoiceData>("/api/voice");
  return <><PageHeader title="Хоолой" sub="AI-ийн ярих хурд, завсар болон үгсийн зөв дуудлагыг тохируулна." /><VoiceSettings initial={data} /></>;
}
