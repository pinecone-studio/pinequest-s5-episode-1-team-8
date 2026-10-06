import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { EmptyState, PageHeader } from "@/components/PageHeader";
import { findNavItem } from "@/lib/nav";
import { requireUser } from "@/lib/session";

// Sidebar-ын хараахан хийгдээгүй хэсгүүд (Яриа, FAQ ...). Хэсэг бүрийг хийхдээ app/(dashboard)/<нэр>/page.tsx
// үүсгэхэд энэ түр хуудсыг орлоно.
export async function generateMetadata({ params }: PageProps<"/[section]">): Promise<Metadata> {
  const { section } = await params;
  return { title: findNavItem(`/${section}`)?.label };
}

export default async function SectionPage({ params }: PageProps<"/[section]">) {
  const user = await requireUser();
  const { section } = await params;
  const item = findNavItem(`/${section}`);
  if (!item || item.href === "/" || (item.adminOnly && user.role !== "admin")) notFound();

  return (
    <>
      <PageHeader title={item.label} />
      <EmptyState>Энэ хэсэг хийгдэж байна.</EmptyState>
    </>
  );
}
