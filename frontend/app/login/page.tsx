import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthCard } from "@/components/auth/AuthCard";
import { LoginForm } from "@/components/auth/LoginForm";
import { getUser } from "@/lib/session";

export const metadata: Metadata = { title: "Нэвтрэх" };

export default async function LoginPage() {
  // Аль хэдийн нэвтэрсэн бол шууд самбар руу. Backend унтарсан бол форм харагдана (алдааг форм хэлнэ).
  const user = await getUser().catch(() => null);
  if (user) redirect("/");

  return (
    <AuthCard
      title="Нэвтрэх"
      sub="Байгууллагынхаа AI ресепшнийг удирдах самбар"
      footer={<>Бүртгэлгүй юу? <Link href="/signup" className="text-brand hover:underline">Байгууллагаа бүртгүүлэх</Link></>}
    >
      <LoginForm />
    </AuthCard>
  );
}
