"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { TrainingAnswers } from "@/lib/types";

/** Залгагчийн асуултад зөв хариултыг заах -> AI сургалтын жишээ (POST /api/train/examples).
 *  Дараагийн "Бэлдэх"-ийн үед (train_selector) AI-д хэрэгжинэ. */
export function TeachAnswer({ question, answers }: { question: string; answers: TrainingAnswers }) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function teach() {
    setError("");
    setMessage("");
    if (!value) return setError("Зөв хариултыг сонгоно уу");
    setPending(true);
    try {
      await apiSend("/api/train/examples", "POST", { q: question, answer: value });
      setMessage("Заалаа ✓ Дараагийн «Бэлдэх»-ийн үед AI-д хэрэгжинэ");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  }

  const groups: [string, TrainingAnswers["faq"]][] = [["Тусгай", answers.special], ["FAQ", answers.faq], ["Мэдээлэл", answers.facts]];
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Зөв хариулт"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="min-w-[220px] flex-1 rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none"
        >
          <option value="">— зөв хариултыг сонгоно уу —</option>
          {groups.map(([label, items]) => items.length > 0 && (
            <optgroup key={label} label={label}>
              {items.map((o) => <option key={o.value} value={o.value}>{o.title}</option>)}
            </optgroup>
          ))}
        </select>
        <Button type="button" onClick={teach} disabled={pending}>{pending ? "Зааж байна…" : "Заах"}</Button>
      </div>
      <ActionStatus error={error} message={message} />
    </div>
  );
}
