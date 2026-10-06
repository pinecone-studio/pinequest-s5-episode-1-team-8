import { TeachAnswer } from "@/components/teach/TeachAnswer";
import type { Message, TrainingAnswers } from "@/lib/types";
import { RouteTag } from "./RouteTag";

/** Яриан дахь нэг мессеж: залгагч баруун талд, AI зүүн талд (ногоон).
 *  answers өгвөл залгагчийн асуулт бүр дээр "Зөв хариултыг заах" (AI сургалт) */
export function ChatMessage({ m, answers }: { m: Message; answers?: TrainingAnswers | null }) {
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
      {user && answers && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-muted hover:text-fg">Зөв хариултыг заах</summary>
          <div className="mt-2 min-w-[min(420px,70vw)]"><TeachAnswer question={m.text} answers={answers} /></div>
        </details>
      )}
    </div>
  );
}
