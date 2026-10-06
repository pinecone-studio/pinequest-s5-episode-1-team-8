"use client";

import type { FormEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { apiSend } from "@/lib/client";
import { useAction } from "@/lib/useAction";

/** Одоогийн + шинэ нууц үг -> POST /api/account/password */
export function PasswordForm() {
  const { pending, error, message, run } = useAction();

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const ok = await run(
      () => apiSend("/api/account/password", "POST", { current: data.get("current"), new: data.get("new") }),
      "Нууц үг солигдлоо ✓",
    );
    if (ok) form.reset();
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3.5 md:grid-cols-2">
      <Field label="Одоогийн нууц үг" name="current" type="password" autoComplete="current-password" required />
      <Field label="Шинэ нууц үг (8+ тэмдэгт)" name="new" type="password" autoComplete="new-password" required minLength={8} />
      <div className="flex flex-wrap items-center gap-3 md:col-span-2">
        <Button type="submit" disabled={pending}>{pending ? "Сольж байна…" : "Солих"}</Button>
        <ActionStatus error={error} message={message} />
        {!error && !message && <span className="text-[13px] text-muted">Бусад төхөөрөмж дээрх нэвтрэлт хүчингүй болно.</span>}
      </div>
    </form>
  );
}
