"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { apiSend } from "@/lib/client";

/**
 * Байгууллагын нэр, утас, и-мэйл, нууц үг, нууц үг давталт
 * -> POST /api/signup
 * -> Тохируулах хуудас руу
 *
 * Password-ийн Харах/Нуух функц нь
 * reusable Field component дотор хийгдсэн.
 */
export function SignupForm() {
  const router = useRouter();

  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const formData = new FormData(e.currentTarget);
    const password = formData.get("password") as string;

    // Хоёр нууц үг ижил эсэхийг шалгах
    if (password !== confirmPassword) {
      setError("Нууц үг таарахгүй байна");
      return;
    }

    // Давтан оруулсан нууц үгийг backend руу явуулах payload-аас хасах зорилгоор objekt болгож авна
    const form = Object.fromEntries(formData.entries());

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
      <Field
        label="Байгууллагын нэр"
        name="company"
        placeholder="Жишээ: Гэрэл шүдний эмнэлэг"
        required
        minLength={2}
        maxLength={80}
        autoFocus
      />

      <Field
        label="Байгууллагын утас (заавал биш)"
        name="phone"
        type="tel"
        placeholder="7xxxxxxx"
      />

      <Field
        label="И-мэйл"
        name="email"
        type="email"
        autoComplete="username"
        placeholder="name@company.mn"
        required
      />

      <Field
        label="Нууц үг (8+ тэмдэгт)"
        name="password"
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
      />

      {/* Нууц үгээ давтах талбар */}
      <Field
        label="Нууц үгээ давтах"
        name="confirmPassword"
        type="password"
        autoComplete="new-password"
        placeholder="Нууц үгээ дахин оруулна уу"
        required
        minLength={8}
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
      />

      {error && <Alert>{error}</Alert>}

      <Button
        type="submit"
        variant="primary"
        size="lg"
        disabled={pending}
        className="mt-1 w-full"
      >
        {pending ? "Бүртгэж байна…" : "Бүртгүүлэх"}
      </Button>
    </form>
  );
}