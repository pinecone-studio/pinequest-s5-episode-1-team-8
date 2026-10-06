"use client";

import type { FormEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { apiSend } from "@/lib/client";
import type { Org } from "@/lib/types";
import { useAction } from "@/lib/useAction";

/** Байгууллагын нэр, утас, и-мэйл, хаяг, цаг -> PUT /api/org */
export function OrgForm({ org }: { org: Org }) {
  const { pending, error, message, run } = useAction();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget));
    run(() => apiSend("/api/org", "PUT", body), "Хадгаллаа ✓ Мэндчилгээ, утас/хаяг/цагийн хариулт шинэчлэгдлээ");
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3.5 md:grid-cols-2">
      <Field label="Нэр" name="name" defaultValue={org.name} required minLength={2} maxLength={80} />
      <Field label="Утас (AI залгагчид хэлнэ)" name="phone" type="tel" defaultValue={org.phone} placeholder="7xxxxxxx" />
      <Field label="И-мэйл" name="email" type="email" defaultValue={org.email} />
      <Field label="Цагийн хуваарь" name="hours" defaultValue={org.hours} placeholder="Даваа-Баасан 09:00-18:00, Бямба 10:00-14:00" maxLength={200} />
      <div className="md:col-span-2">
        <Field label="Хаяг" name="address" defaultValue={org.address} placeholder="Сүхбаатар дүүрэг, ... байр, 4 давхар" maxLength={300} />
      </div>
      <div className="flex flex-wrap items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" disabled={pending}>
          {pending ? "Хадгалж байна…" : "Хадгалах"}
        </Button>
        <ActionStatus error={error} message={message} />
        {!error && !message && (
          <span className="text-[13px] text-muted">Мэндчилгээ, утас/хаяг/цагийн хариулт автоматаар үүснэ.</span>
        )}
      </div>
    </form>
  );
}
