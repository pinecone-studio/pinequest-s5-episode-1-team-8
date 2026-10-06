import type { ReactNode, TdHTMLAttributes } from "react";

/** Хүснэгт: нарийн дэлгэц дээр хөндлөн гүйлгэнэ */
export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} className="border-b border-line-2 px-2.5 py-2.5 text-left font-mono text-[11px] font-medium tracking-[.1em] text-muted uppercase">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr:last-child>td]:border-b-0">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({ className = "", ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`border-b border-line px-2.5 py-3 align-top ${className}`} {...props} />;
}
