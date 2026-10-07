import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { VoiceSettings } from "@/components/voice/VoiceSettings";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { ElevenStatus, VoiceData } from "@/lib/types";

export const metadata: Metadata = { title: "Хоолой" };

export default async function VoicePage({ searchParams }: PageProps<"/voice">) {
  const user = await requireUser();
  const { tab } = await searchParams;
  const isAdmin = user.role === "admin";
  const [data, eleven] = await Promise.all([
    apiGet<VoiceData>("/api/voice"),
    isAdmin ? apiGet<ElevenStatus>("/api/admin/eleven").catch(() => null) : Promise.resolve(null),
  ]);
  return (
    <>
      <PageHeader
        title="Хоолой"
        sub="Залгагчид тоглогдох бүх аудио: хоолойгоо сонгох, чанарыг нь шалгах, дуудлагыг засах. ElevenLabs-ийг зөвхөн аудио бэлдэхэд ашиглана."
        actions={
          <a href="/api/voice/export" download
            className="inline-flex items-center rounded-[10px] border-[1.5px] border-line-2 px-4 py-[9px] text-sm font-semibold hover:border-brand">
            ⬇ ZIP татах
          </a>
        }
      />
      <VoiceSettings initial={data} eleven={eleven} isAdmin={isAdmin} initialTab={typeof tab === "string" ? tab : undefined} />
    </>
  );
}
