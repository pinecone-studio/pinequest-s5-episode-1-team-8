import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/auth/LoginForm";
import { Brand } from "@/components/Brand";
import { getUser } from "@/lib/session";

export const metadata: Metadata = { title: "Нэвтрэх" };

export default async function LoginPage() {
  // Аль хэдийн нэвтэрсэн бол шууд самбар руу. Backend унтарсан бол форм харагдана (алдааг форм хэлнэ).
  const user = await getUser().catch(() => null);
  if (user) redirect("/");

  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(600px_360px_at_50%_0%,rgba(95,214,143,.08),transparent_70%)] px-4 py-6">
      <div className="flex w-full max-w-[400px] flex-col gap-4 rounded-2xl border border-line bg-panel px-7 py-8">
        <div className="pb-2">
          <Brand />
        </div>
        <div>
          <h1 className="mb-1 text-[26px] font-extrabold tracking-[-.01em]">Нэвтрэх</h1>
          <p className="text-sm text-muted">Байгууллагынхаа AI ресепшнийг удирдах самбар</p>
        </div>
        <LoginForm />
      </div>
    </main>
  );
}
