"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiSend } from "@/lib/client";

/** «Мартагдах эрх»: тэр хүний бүх мэдээллийг (бүх бүртгэл, код, хувийн RAG, яриа) бүрэн устгана */
export function ForgetPerson({ leadId, name }: { leadId: number; name: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function forget() {
    if (!window.confirm(`${name || "Энэ хүн"}-ий бүх мэдээллийг (бүх бүртгэл, код, хувийн баримт, яриа) бүрмөсөн устгах уу? Буцаах боломжгүй.`)) return;
    setBusy(true);
    setError("");
    try {
      await apiSend(`/api/database/person/${leadId}`, "DELETE");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Алдаа");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="mt-1.5">
      <button type="button" disabled={busy} onClick={forget} className="cursor-pointer text-[13px] text-muted hover:text-danger disabled:opacity-50">
        🗑 Мэдээллийг устгах
      </button>
      {error && <div className="text-[13px] text-danger">{error}</div>}
    </div>
  );
}
