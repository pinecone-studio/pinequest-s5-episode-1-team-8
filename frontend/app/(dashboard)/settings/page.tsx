import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { OutboundSettings } from "@/components/settings/OutboundSettings";
import { PasswordForm } from "@/components/settings/PasswordForm";
import { ReminderTemplate } from "@/components/settings/ReminderTemplate";
import { TelegramSettings } from "@/components/settings/TelegramSettings";
import { Card } from "@/components/ui/Card";
import { Tag } from "@/components/ui/Tag";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { OutboundConfig, RemindersData, Settings } from "@/lib/types";

export const metadata: Metadata = { title: "Тохиргоо" };

export default async function SettingsPage() {
  const user = await requireUser();
  const [st, reminders, outbound] = await Promise.all([
    apiGet<Settings>("/api/settings"),
    apiGet<RemindersData>("/api/reminders"),
    user.role === "admin" ? apiGet<OutboundConfig>("/api/admin/outbound") : Promise.resolve(null),
  ]);
  return (
    <>
      <PageHeader
        title="Тохиргоо"
        sub="Шинэ бүртгэл, ажилтан эргэж залгах хүсэлт ирэхэд ажилтнуудын Telegram групп руу мэдэгдэл илгээнэ."
      />
      <Section
        title="Telegram мэдэгдэл"
        aside={
          st.telegram_chat_id ? (
            <Tag>Идэвхтэй · {st.telegram_chat_title || st.telegram_chat_id}</Tag>
          ) : (
            <Tag tone="gray">{st.telegram_token_set ? `@${st.telegram_bot} · групп сонгоогүй` : "Тохируулаагүй"}</Tag>
          )
        }
      >
        <Card>
          <TelegramSettings settings={st} />
        </Card>
      </Section>
      <Section title="AI сануулгын мессеж" aside={<Tag tone="gray">Бүртгэл → Уулзалт товлох</Tag>}>
        <Card>
          <ReminderTemplate initial={reminders.template} fallback={reminders.default_template} />
        </Card>
      </Section>
      {outbound && (
        <Section title="Гарах дуудлага (admin)" aside={<Tag tone={outbound.mode === "off" ? "gray" : "ok"}>{outbound.mode === "sip" ? "GSM gateway / SIP" : outbound.mode === "mac" ? "iMac + iPhone" : "Унтраалттай"}</Tag>}>
          <Card>
            <OutboundSettings initial={outbound} />
          </Card>
        </Section>
      )}
      <Section title="Нууц үг солих" aside={user.email}>
        <Card>
          <PasswordForm />
        </Card>
      </Section>
    </>
  );
}
