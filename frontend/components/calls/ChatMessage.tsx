import type { Message } from "@/lib/types";
import { RouteTag } from "./RouteTag";

/** Яриан дахь нэг мессеж: залгагч баруун талд, AI зүүн талд (ногоон) */
export function ChatMessage({ m }: { m: Message }) {
  const user = m.role === "user";
  return (
    <div
      className={`max-w-[72%] rounded-[14px] px-4 py-3 max-md:max-w-[92%] ${
        user
          ? "self-end rounded-br-[4px] bg-panel-2"
          : "self-start rounded-bl-[4px] border border-brand/25 bg-brand/12"
      }`}
    >
      {m.text}
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 font-mono text-xs text-muted">
        {user ? (
          <>Залгагч{m.stt_sec != null && ` · STT ${m.stt_sec.toFixed(1)}с`}</>
        ) : (
          <>
            AI <RouteTag route={m.route} />
            {m.score != null && ` · оноо ${m.score.toFixed(2)}`}
            {m.latency != null && ` · ${m.latency.toFixed(1)}с`}
          </>
        )}
      </div>
    </div>
  );
}
