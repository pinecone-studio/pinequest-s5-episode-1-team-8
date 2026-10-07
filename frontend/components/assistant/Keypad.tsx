"use client";

import { useState } from "react";

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"];

/** Утасны товчлуур: код, дугаар (бүтэн) эсвэл цэсний сонголт (1 товч) */
export function Keypad({ need, disabled, onSubmit }: { need: number; disabled: boolean; onSubmit: (digits: string) => void }) {
  return <KeypadInner key={need} need={need} disabled={disabled} onSubmit={onSubmit} />;
}

function KeypadInner({ need, disabled, onSubmit }: { need: number; disabled: boolean; onSubmit: (digits: string) => void }) {
  const [buf, setBuf] = useState("");
  const press = (k: string) => {
    if (k === "*") return setBuf("");
    if (k === "#") {
      if (buf) onSubmit(buf);
      return setBuf("");
    }
    const next = buf + k;
    if (need <= 1 || next.length >= need) {
      setBuf("");
      onSubmit(next);
    } else setBuf(next);
  };
  return (
    <div>
      <div className="mb-2 flex h-9 items-center justify-between rounded-[10px] bg-bg px-3 font-mono text-lg tracking-[0.3em]">
        <span>{buf ? "•".repeat(buf.length) : <span className="text-[13px] tracking-normal text-dim">{need > 1 ? `${need} цифр` : "1 товч"}</span>}</span>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {KEYS.map((k) => (
          <button
            key={k}
            type="button"
            disabled={disabled}
            onClick={() => press(k)}
            className="cursor-pointer rounded-[10px] border-[1.5px] border-line-2 py-2 font-mono text-lg hover:border-brand disabled:cursor-default disabled:opacity-40"
          >
            {k}
          </button>
        ))}
      </div>
    </div>
  );
}
