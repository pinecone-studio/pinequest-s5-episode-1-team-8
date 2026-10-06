import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { PasswordForm } from "@/components/settings/PasswordForm";
import { Card } from "@/components/ui/Card";
import { requireUser } from "@/lib/session";

export const metadata: Metadata = { title: "Тохиргоо" };

export default async function SettingsPage() {
  const user = await requireUser();
  return (
    <>
      <PageHeader title="Тохиргоо" sub="Бүртгэлийн нууц үг, мэдэгдлийн тохиргоо." />
      <Section title="Нууц үг солих" aside={user.email}>
        <Card>
          <PasswordForm />
        </Card>
      </Section>
    </>
  );
}
