import type { ReactNode } from "react";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { apiGet } from "@/lib/api";
import type { Badges } from "@/lib/nav";
import { requireUser } from "@/lib/session";

// Нэвтэрсний дараах бүх хуудас: зүүн талд sidebar, баруун талд хуудас
export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();
  // Тоон тэмдэг: алдаа гарвал (backend хуучин) цэс тоогүй харагдана. Хадгалах үйлдлийн дараа шинэчлэгдэнэ (router.refresh).
  const badges = await apiGet<Badges>("/api/stats").catch(() => null);
  return (
    <div className="flex min-h-screen max-md:flex-col">
      <Sidebar user={user} badges={badges} />
      <main className="max-w-[1500px] min-w-0 flex-1 px-16 pt-[46px] pb-16 max-xl:px-7 max-xl:pt-8 max-md:px-4 max-md:pt-6">
        {children}
      </main>
    </div>
  );
}
