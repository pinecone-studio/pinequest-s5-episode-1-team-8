"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiSend } from "@/lib/client";
import { refreshStatus } from "@/lib/useStatus";

/** Admin өөр байгууллагыг харж байх үед хуудасны дээр: андуурч өөр байгууллагын өгөгдлийг засахаас сэргийлнэ */
export function ViewingBanner({ name }: { name: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function back() {
    setPending(true);
    try {
      await apiSend("/api/admin/switch", "DELETE");
      router.push("/");
      router.refresh();
      void refreshStatus();
    } finally {
      setPending(false);
    }
  }

  return (
    <div role="status" className="mb-6 flex flex-wrap items-center gap-3 rounded-[12px] border border-warn/40 bg-warn/12 px-4 py-3 text-sm">
      <span className="min-w-0 flex-1">
        Та <b>«{name}»</b> байгууллагыг admin эрхээр харж байна. Энд хийсэн өөрчлөлт тэр байгууллагад хадгалагдана.
      </span>
      <button type="button" onClick={back} disabled={pending} className="cursor-pointer font-semibold text-warn hover:underline disabled:opacity-50">
        Өөрийнхөө руу буцах
      </button>
    </div>
  );
}
