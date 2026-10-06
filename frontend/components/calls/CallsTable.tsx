import Link from "next/link";
import { EmptyState } from "@/components/PageHeader";
import { Table, Td } from "@/components/ui/Table";
import { Tag } from "@/components/ui/Tag";
import { formatDateTime, formatSeconds } from "@/lib/format";
import type { Call } from "@/lib/types";

/** Дуудлагын хүснэгт. Мөр дээр дарахад тухайн дуудлагын яриа нээгдэнэ. */
export function CallsTable({ calls }: { calls: Call[] }) {
  if (!calls.length) return <EmptyState>Дуудлага алга. Zoiper-оос дотуур дугаар руу залгаж туршаарай.</EmptyState>;
  return (
    <Table head={["Хэзээ", "Залгагч", "Үргэлжилсэн", "Асуулт", "Хариулж чадаагүй"]}>
      {calls.map((c) => (
        <tr key={c.uuid} className="relative hover:bg-panel-2">
          <Td className="font-mono text-sm">
            {/* мөр бүхэлдээ дарагдана (after: бүх мөрийг бүрхэнэ) */}
            <Link href={`/calls/${c.uuid}`} className="after:absolute after:inset-0">
              {formatDateTime(c.started_at)}
            </Link>
          </Td>
          <Td>{c.caller || "—"}</Td>
          <Td className="font-mono text-sm">{formatSeconds(c.duration)}</Td>
          <Td className="font-mono text-sm">{c.questions}</Td>
          <Td>{c.unanswered ? <Tag tone="warn">{c.unanswered}</Tag> : <span className="font-mono text-sm">0</span>}</Td>
        </tr>
      ))}
    </Table>
  );
}
