"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";

/**
 * «Демо» товч -> POST /api/demo-login (нууц үггүй)
 * Багш, шүүгч admin-аар бүх хэсгийг харна; засах, устгах эрхгүй (backend хаана).
 */
export function DemoLogin() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onClick() {
    setPending(true);
    setError("");
    try {
      await apiSend("/api/demo-login", "POST");
      router.replace("/");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-line" />
        эсвэл
        <span className="h-px flex-1 bg-line" />
      </div>
      <Button type="button" size="lg" disabled={pending} onClick={onClick} className="w-full">
        {pending ? "Нэвтэрч байна…" : "Демо"}
      </Button>
      <p className="text-center text-xs text-muted">Нууц үггүйгээр орж харах (засах боломжгүй)</p>
      {error && <Alert>{error}</Alert>}
    </div>
  );
}
