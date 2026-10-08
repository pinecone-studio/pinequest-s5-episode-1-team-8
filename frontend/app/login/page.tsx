import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthCard } from "@/components/auth/AuthCard";
import { DemoLogin } from "@/components/auth/DemoLogin";
import { LoginForm } from "@/components/auth/LoginForm";
import { API_URL } from "@/lib/config";
import { getUser } from "@/lib/session";

export const metadata: Metadata = { title: "Нэвтрэх" };

/** «Демо» товч харагдах эсэх (backend DEMO_LOGIN). Backend унтарсан бол харуулахгүй. */
async function demoEnabled(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/demo`, { cache: "no-store" });
    return res.ok && (await res.json()).enabled === true;
  } catch {
    return false;
  }
}

export default async function LoginPage() {
  // Аль хэдийн нэвтэрсэн бол шууд самбар руу. Backend унтарсан бол форм харагдана (алдааг форм хэлнэ).
  const user = await getUser().catch(() => null);
  if (user) redirect("/");
  const demo = await demoEnabled();

  return (
    <AuthCard
      title="Нэвтрэх"
      sub="Байгууллагынхаа AI ресепшнийг удирдах самбар"
      footer={<>Бүртгэлгүй юу? <Link href="/signup" className="text-brand hover:underline">Байгууллагаа бүртгүүлэх</Link></>}
    >
      <LoginForm />
      {demo && <DemoLogin />}
    </AuthCard>
  );
}
