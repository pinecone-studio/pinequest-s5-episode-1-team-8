"use client";

import { useId, useState, type InputHTMLAttributes } from "react";

const INPUT =
  "w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2.5 text-sm text-fg placeholder:text-dim focus:border-brand focus:outline-none";

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string };

/** Шошготой input. type="password" бол "Харуулах" товчтой. */
export function Field({ label, type = "text", className = "", ...props }: Props) {
  const id = useId();
  const [shown, setShown] = useState(false);
  const isPassword = type === "password";

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-semibold text-muted">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={isPassword && shown ? "text" : type}
          className={`${INPUT} ${isPassword ? "pr-20" : ""} ${className}`}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShown((s) => !s)}
            aria-pressed={shown}
            className="absolute inset-y-0 right-1.5 my-auto h-7 cursor-pointer rounded-md px-2 text-xs font-semibold text-muted hover:bg-panel-2 hover:text-fg"
          >
            {shown ? "Нуух" : "Харуулах"}
          </button>
        )}
      </div>
    </div>
  );
}
