"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { refreshStatus } from "./useStatus";

/** Хадгалах, устгах зэрэг үйлдэл: явж байгаа эсэх, алдаа, амжилтын мессеж.
 *  Амжилттай бол хуудсын өгөгдөл, sidebar-ын төлөвийг backend-ээс дахин уншина. */
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
      void refreshStatus(); // sidebar-ын тоо (бүртгэл, хариулж чадаагүй)
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
