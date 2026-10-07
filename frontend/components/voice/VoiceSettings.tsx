"use client";

import { useState } from "react";
import { BuildPanel } from "@/components/knowledge/BuildPanel";
import { ActionStatus } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { apiSend } from "@/lib/client";
import { formatDateTime } from "@/lib/format";
import type { ElevenStatus, VoiceData } from "@/lib/types";
import { ClipList } from "./ClipList";
import { ElevenPanel } from "./ElevenPanel";
import { LexiconEditor } from "./LexiconEditor";
import { usePlayer } from "./usePlayer";

type Tab = "clips" | "voice" | "lexicon";
const TABS: [Tab, string][] = [["clips", "Өгүүлбэрүүд"], ["voice", "Хоолой сонгох"], ["lexicon", "Дуудлагын толь"]];

/** Хоолой: залгагчид тоглогдох бүх аудио — ElevenLabs (анхдагч Уянга) эсвэл өөрийн бичлэг. Oron TTS ашиглахгүй. */
export function VoiceSettings({ initial, eleven, isAdmin }: { initial: VoiceData; eleven: ElevenStatus | null; isAdmin: boolean }) {
  const [data, setData] = useState(initial);
  const [tab, setTab] = useState<Tab>("clips");
  const [buildKey, setBuildKey] = useState(0); // "Аудиог шинэчлэх"-ийг өөр газраас эхлүүлбэл төлөвийг дахин уншина
  const { play, error } = usePlayer();

  const refresh = async () => setData(await apiSend<VoiceData>("/api/voice", "GET"));
  const recorded = data.items.filter((i) => i.recorded).length;
  const flagged = data.items.filter((i) => i.flags.length && !i.recorded).length;
  const voiceName = data.voice.name ?? "—";

  return (
    <div className="space-y-7">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <div className="text-[24px] font-extrabold">{data.voice.has_key ? `Eleven · ${voiceName}` : "Түлхүүр алга"}</div>
          <div className="text-sm text-muted">
            {data.voice.has_key ? `${data.items.length - recorded} ElevenLabs` : "ElevenLabs түлхүүр оруулна уу (admin)"}
            {recorded ? ` · ${recorded} бичлэг` : ""}
          </div>
        </Card>
        <Card>
          <div className="text-[24px] font-extrabold">{flagged ? `⚠ ${flagged}` : "✓ 0"}</div>
          <div className="text-sm text-muted">шалгах шаардлагатай клип{data.qa_at ? ` · ${formatDateTime(data.qa_at)}` : ""}</div>
        </Card>
        <Card>
          <div className="text-[24px] font-extrabold">{recorded}<span className="text-[15px] font-normal text-muted"> / {data.items.length}</span></div>
          <div className="text-sm text-muted">өөрийн хоолойгоор бичсэн</div>
        </Card>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-line" role="tablist">
        {TABS.map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
            className={`-mb-px cursor-pointer border-b-2 px-4 py-2.5 font-semibold ${tab === key ? "border-brand text-fg" : "border-transparent text-muted hover:text-fg"}`}>
            {label}
          </button>
        ))}
      </div>

      {error && <ActionStatus error={error} />}
      {tab === "clips" && <ClipList items={data.items} voiceName={voiceName} play={play} onChange={refresh} />}
      {tab === "voice" && (isAdmin && eleven
        ? <ElevenPanel initial={eleven} play={play} onRebuild={async () => { await refresh(); setBuildKey((k) => k + 1); }} />
        : (
          <Card>
            <h2 className="font-semibold">Одоогийн хоолой: {data.voice.has_key ? `ElevenLabs · ${voiceName}` : "тохируулаагүй"}</h2>
            <p className="mt-2 text-muted">
              ElevenLabs-ийн хоолой сонгох, туршихыг платформын admin тохируулна. Өгүүлбэр бүрийг «Өгүүлбэрүүд» табаас сонсож болно.
            </p>
          </Card>
        ))}
      {tab === "lexicon" && <LexiconEditor settings={data.settings} onSaved={refresh} />}

      <BuildPanel key={buildKey} startPath="/api/voice/rebuild" title="Аудиог шинэчлэх" buttonLabel="Аудиог шинэчлэх"
        description="Хоолойн сонголт, толь, бичлэг, ↻-ийн дагуу өөрчлөгдсөн өгүүлбэрүүдийг ElevenLabs-аар дахин үүсгэнэ (кэштэйг алгасна, AI-г дахин сургахгүй). Шинэ мэдээлэл нэмсэн бол Тохируулах → «Аудио бэлдэх»." />
    </div>
  );
}
