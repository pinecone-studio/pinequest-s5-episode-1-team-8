import type { Metadata } from "next";
import Link from "next/link";
import { RouteTag } from "@/components/calls/RouteTag";
import { EmptyState, PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/Card";
import { Table, Td } from "@/components/ui/Table";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { requireUser } from "@/lib/session";
import type { Unanswered } from "@/lib/types";

export const metadata: Metadata = { title: "Хариулж чадаагүй" };

export default async function UnansweredPage() {
  await requireUser();
  const items = await apiGet<Unanswered[]>("/api/unanswered");
  return (
    <>
      <PageHeader
        title="Хариулж чадаагүй"
        sub="AI дахин асуусан, тодруулсан эсвэл ажилтанд шилжүүлсэн асуултууд. Асуулт дээр дарж бүх яриаг харна. Мэдээлэлд огт байхгүй бол Мэдээлэл хэсэгт нэмнэ."
        actions={<Link href="/knowledge" className="font-bold hover:underline">Мэдээлэл нэмэх →</Link>}
      />
      <Card>
        {items.length ? (
          <Table head={["Асуулт (STT)", "AI", "Хэзээ"]}>
            {items.map((u) => (
              <tr key={u.id} className="hover:bg-panel-2">
                <Td>
                  <Link href={`/calls/${u.call_uuid}`} className="text-brand hover:underline">{u.question}</Link>
                </Td>
                <Td><RouteTag route={u.route} /></Td>
                <Td className="font-mono text-sm whitespace-nowrap text-muted">{formatDateTime(u.ts)}</Td>
              </tr>
            ))}
          </Table>
        ) : (
          <EmptyState>Хариулж чадаагүй асуулт алга 🎉</EmptyState>
        )}
      </Card>
    </>
  );
}
