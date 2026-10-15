import type { ReactNode, TdHTMLAttributes } from "react";

/** Хүснэгт: утасны дэлгэц дээр (md-ээс нарийн) мөр бүр карт болж, нүднүүд дээрээс доош байрлана —
 *  хөндлөн гүйлгэвэл утас, төлөв, тэмдэглэл баганууд харагдахгүй байсан. */
const STACK =
  "max-md:[&_table]:block max-md:[&_thead]:hidden max-md:[&_tbody]:block " +
  "max-md:[&_tbody>tr]:mb-3 max-md:[&_tbody>tr]:block max-md:[&_tbody>tr]:rounded-[12px] max-md:[&_tbody>tr]:border " +
  "max-md:[&_tbody>tr]:border-line max-md:[&_tbody>tr]:bg-panel max-md:[&_tbody>tr]:p-3 " +
  "max-md:[&_td]:block max-md:[&_td]:min-w-0 max-md:[&_td]:border-0 max-md:[&_td]:px-0 max-md:[&_td]:py-1.5";

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className={`overflow-x-auto ${STACK}`}>
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
