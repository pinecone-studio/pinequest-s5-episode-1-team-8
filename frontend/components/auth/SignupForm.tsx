"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { apiSend } from "@/lib/client";

/** Байгууллагын нэр, утас, и-мэйл, нууц үг -> POST /api/signup -> Тохируулах хуудас руу */
export function SignupForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = Object.fromEntries(new FormData(e.currentTarget));
    setPending(true);
    setError("");
    try {
      await apiSend("/api/signup", "POST", form);
      router.replace("/setup");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <Field label="Байгууллагын нэр" name="company" placeholder="Жишээ: Гэрэл шүдний эмнэлэг" required minLength={2} maxLength={80} autoFocus />
      <Field label="Байгууллагын утас (заавал биш)" name="phone" type="tel" placeholder="7xxxxxxx" />
      <Field label="И-мэйл" name="email" type="email" autoComplete="username" placeholder="name@company.mn" required />
      <Field label="Нууц үг (8+ тэмдэгт)" name="password" type="password" autoComplete="new-password" required minLength={8} />
      {error && <Alert>{error}</Alert>}
      <Button type="submit" variant="primary" size="lg" disabled={pending} className="mt-1 w-full">
        {pending ? "Бүртгэж байна…" : "Бүртгүүлэх"}
      </Button>
    </form>
  );
}
