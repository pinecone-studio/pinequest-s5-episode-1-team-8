"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { BuildEstimate, BuildStatus } from "@/lib/types";
import { refreshStatus } from "@/lib/useStatus";

/** "Бэлдэх": мэдээллээс индекс, FAQ, аудио бэлдэж AI-г сургана (backend: /api/knowledge/build).
 *  Эхлээд ElevenLabs-аар шинээр үүсэх өгүүлбэрийг тоолж (токен), байвал асууна. Явагдаж байх үед 2с тутам лог шинэчилнэ. */
export function BuildPanel({ initial }: { initial: BuildStatus }) {
  const router = useRouter();
  const [build, setBuild] = useState(initial);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [estimate, setEstimate] = useState<BuildEstimate | null>(null);
  const [checking, setChecking] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (!build.running) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await apiSend<BuildStatus>("/api/knowledge/build", "GET");
        setBuild(next);
        if (!next.running) {
          if (next.state === "done") setMessage("Бэлэн боллоо ✓");
          else if (next.state === "canceled") setMessage("Зогсоолоо — өмнө бэлдсэн аудио хэвээр ажиллана");
          else setError(`Алдаа гарлаа (код ${next.code}). Логийг шалгана уу.`);
          router.refresh();
          void refreshStatus();
        }
      } catch (err) {
        setError((err as Error).message);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [build.running, router]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [build.log]);

  async function start() {
    setError("");
    setMessage("");
    try {
      setChecking(true);
      const est = await apiSend<BuildEstimate>("/api/knowledge/build/estimate", "GET").catch(() => null);
      setChecking(false);
      setEstimate(est);
      if (est?.new && !window.confirm(`${est.new} өгүүлбэр (~${est.chars} тэмдэгт) ElevenLabs-аар шинээр үүснэ — токен зарцуулна. `
        + `Бусад ${est.cached + est.recorded} нь бэлэн. Үргэлжлүүлэх үү?`)) return;
      setBuild(await apiSend<BuildStatus>("/api/knowledge/build", "POST"));
      void refreshStatus();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function cancel() {
    if (!window.confirm("Бэлдэж буй ажлыг зогсоох уу? Өмнө бэлдсэн аудио хэвээр ажиллана, дараа нь дахин бэлдэж болно.")) return;
    setError("");
    try {
      setBuild(await apiSend<BuildStatus>("/api/knowledge/build/cancel", "POST"));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const log = build.state === "queued" ? `Дараалалд байна (өмнө нь ${build.ahead} ажил)...` : build.log.join("\n") || "—";
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={start} disabled={build.running || checking}>
          {checking ? "Тооцоолж байна..." : build.state === "queued" ? "Дараалалд..." : build.running ? "Бэлдэж байна..." : "Бэлдэх"}
        </Button>
        {build.running && <Button onClick={cancel} className="hover:border-danger hover:text-danger">⏹ Зогсоох</Button>}
        {estimate && (
          <span className="text-sm text-muted">
            {estimate.new ? `ElevenLabs: ${estimate.new} шинэ өгүүлбэр (~${estimate.chars} тэмдэгт)` : "Аудио бүгд бэлэн — токен зарцуулахгүй"}
            {` · ${estimate.cached} кэштэй${estimate.recorded ? ` · ${estimate.recorded} бичлэг` : ""}`}
          </span>
        )}
        <ActionStatus error={error} message={message} />
      </div>
      <pre ref={logRef} className="max-h-[260px] overflow-auto rounded-[10px] bg-bg px-3.5 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted">
        {log}
      </pre>
    </div>
  );
}
