import type { ReactNode } from "react";

/** Жижиг дөрвөлжин товч: ▶ сонсох, ☎ утасны чанар, ● бичих, ↻ дахин үүсгэх */
export function IconButton({ label, danger = false, active = false, disabled = false, onClick, children }: {
  label: string;
  danger?: boolean;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button type="button" title={label} aria-label={label} onClick={onClick} disabled={disabled}
      className={`grid size-10 shrink-0 cursor-pointer place-items-center rounded-[10px] border font-semibold disabled:cursor-default disabled:opacity-45 ${
        danger ? "border-danger/50 text-danger" : "border-line-2"} ${active ? "bg-danger/15" : "bg-transparent hover:border-brand"}`}>
      {children}
    </button>
  );
}
