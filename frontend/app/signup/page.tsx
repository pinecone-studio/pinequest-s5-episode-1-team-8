import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthCard } from "@/components/auth/AuthCard";
import { SignupForm } from "@/components/auth/SignupForm";
import { getUser } from "@/lib/session";

export const metadata: Metadata = { title: "Байгууллага бүртгүүлэх" };

export default async function SignupPage() {
  const user = await getUser().catch(() => null);
  if (user) redirect("/");

  return (
    <AuthCard
      title="Байгууллага бүртгүүлэх"
      sub="Бүртгүүлээд мэдээллээ оруулахад өөрийн AI ресепшнтэй болно. Код, AI мэдлэг шаардлагагүй."
      footer={<>Бүртгэлтэй юу? <Link href="/login" className="text-brand hover:underline">Нэвтрэх</Link></>}
    >
      <SignupForm />
    </AuthCard>
  );
}
