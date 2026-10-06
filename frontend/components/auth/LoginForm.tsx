"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";

const OFFLINE = "Сервертэй холбогдож чадсангүй. Түр хүлээгээд дахин оролдоно уу.";

/** И-мэйл + нууц үг -> POST /api/login (backend httpOnly cookie тавина) -> самбар руу */
export function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setPending(true);
    setError("");
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      if (res.ok) {
        router.replace("/");
        router.refresh();
        return; // самбар ачаалагдтал товч идэвхгүй хэвээр
      }
      const body = await res.json().catch(() => null);
      setError(body?.detail ?? OFFLINE);
    } catch {
      setError(OFFLINE);
    }
    setPending(false);
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <Field label="И-мэйл" name="email" autoComplete="username" placeholder="name@company.mn" required autoFocus />
      <Field label="Нууц үг" name="password" type="password" autoComplete="current-password" placeholder="••••••••" required />
      {error && <Alert>{error}</Alert>}
      <Button type="submit" variant="primary" size="lg" disabled={pending} className="mt-1 w-full">
        {pending ? "Нэвтэрч байна…" : "Нэвтрэх"}
      </Button>
    </form>
  );
}
