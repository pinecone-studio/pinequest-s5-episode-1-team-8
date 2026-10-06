"use client";

import { useState, type FormEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { apiSend } from "@/lib/client";
import { useAction } from "@/lib/useAction";

/** Admin: шинэ байгууллага + эзэмшигч (төлбөр төлсөн хүн) -> POST /api/admin/tenants */
export function NewTenantForm() {
  const { pending, error, message, run } = useAction();
  const [open, setOpen] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const body = Object.fromEntries(new FormData(form));
    const ok = await run(() => apiSend("/api/admin/tenants", "POST", body), `«${body.name}» нэмэгдлээ ✓`);
    if (ok) {
      form.reset();
      setOpen(false);
    }
  }

  if (!open) {
    return (
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Button type="button" variant="primary" onClick={() => setOpen(true)}>+ Байгууллага нэмэх</Button>
        <ActionStatus error={error} message={message} />
      </div>
    );
  }

  return (
    <Card className="mb-4">
      <form onSubmit={onSubmit} className="grid gap-3.5 md:grid-cols-2">
        <h3 className="font-semibold md:col-span-2">Байгууллага</h3>
        <Field label="Нэр" name="name" required minLength={2} maxLength={80} />
        <Field label="Утас" name="phone" type="tel" placeholder="7xxxxxxx" />
        <Field label="Албан и-мэйл" name="email" type="email" placeholder="info@..." />
        <Field label="Цагийн хуваарь" name="hours" placeholder="Даваа-Баасан 09:00-18:00" maxLength={200} />
        <div className="md:col-span-2">
          <Field label="Хаяг" name="address" placeholder="Сүхбаатар дүүрэг, ... байр, 4 давхар" maxLength={300} />
        </div>
        <h3 className="mt-2 font-semibold md:col-span-2">Эзэмшигч (төлбөр төлсөн хүн)</h3>
        <Field label="И-мэйл (нэвтрэх нэр)" name="owner_email" type="email" required />
        <Field label="Нууц үг" name="password" type="password" required minLength={8} autoComplete="new-password" />
        <div className="flex flex-wrap items-center gap-3 md:col-span-2">
          <Button type="submit" variant="primary" disabled={pending}>
            {pending ? "Нэмж байна…" : "Нэмэх"}
          </Button>
          <Button type="button" onClick={() => setOpen(false)} disabled={pending}>Болих</Button>
          <ActionStatus error={error} message={message} />
        </div>
      </form>
    </Card>
  );
}
