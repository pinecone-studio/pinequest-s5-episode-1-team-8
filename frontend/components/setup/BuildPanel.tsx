"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { BuildStatus } from "@/lib/types";
import { refreshStatus } from "@/lib/useStatus";

/** "Бэлдэх": мэдээллээс индекс, FAQ, аудио бэлдэж AI-г сургана (backend: /api/knowledge/build).
 *  Явагдаж байх үед 2с тутам лог шинэчилнэ. */
export function BuildPanel({ initial }: { initial: BuildStatus }) {
  const router = useRouter();
  const [build, setBuild] = useState(initial);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (!build.running) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await apiSend<BuildStatus>("/api/knowledge/build", "GET");
        setBuild(next);
        if (!next.running) {
          if (next.state === "done") setMessage("Бэлэн боллоо ✓");
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
      setBuild(await apiSend<BuildStatus>("/api/knowledge/build", "POST"));
      void refreshStatus();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const log = build.state === "queued" ? `Дараалалд байна (өмнө нь ${build.ahead} ажил)...` : build.log.join("\n") || "—";
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={start} disabled={build.running}>
          {build.state === "queued" ? "Дараалалд..." : build.running ? "Бэлдэж байна..." : "Бэлдэх"}
        </Button>
        <ActionStatus error={error} message={message} />
      </div>
      <pre ref={logRef} className="max-h-[260px] overflow-auto rounded-[10px] bg-bg px-3.5 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted">
        {log}
      </pre>
    </div>
  );
}
