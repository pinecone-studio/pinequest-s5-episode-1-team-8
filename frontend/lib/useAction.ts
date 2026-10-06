"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Хадгалах, устгах зэрэг үйлдэл: явж байгаа эсэх, алдаа, амжилтын мессеж.
 *  Амжилттай бол хуудсын өгөгдлийг backend-ээс дахин уншина (router.refresh). */
export function useAction() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function run(fn: () => Promise<unknown>, okMessage = "Хадгаллаа ✓") {
    setPending(true);
    setError("");
    setMessage("");
    try {
      await fn();
      setMessage(okMessage);
      router.refresh();
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setPending(false);
    }
  }

  return { pending, error, message, run };
}
