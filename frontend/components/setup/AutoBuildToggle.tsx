"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { apiSend } from "@/lib/client";

/** Нэмэлт: мэдээлэл, FAQ, байгууллагын мэдээлэл өөрчлөгдөхөд ~30с-ийн дараа автоматаар "Бэлдэх" */
export function AutoBuildToggle({ initial, telegram }: { initial: boolean; telegram: boolean }) {
  const [enabled, setEnabled] = useState(initial);
  const [error, setError] = useState("");

  async function toggle(next: boolean) {
    setError("");
    setEnabled(next);
    try {
      await apiSend("/api/settings/auto-build", "PUT", { enabled: next });
    } catch (err) {
      setEnabled(!next);
      setError((err as Error).message);
    }
  }

  return (
    <div className="mb-4 rounded-[10px] bg-bg px-4 py-3 text-sm">
      <label className="flex cursor-pointer items-center gap-2.5 font-semibold">
        <input type="checkbox" className="size-4 accent-brand" checked={enabled} onChange={(e) => void toggle(e.target.checked)} />
        Мэдээлэл өөрчлөгдөхөд автоматаар бэлдэх
      </label>
      <p className="mt-1.5 text-muted">
        Файл оруулах, засах, FAQ хадгалахад ~30 секундын дараа өөрөө эхэлнэ (олон өөрчлөлтийг нэг удаа).{" "}
        {telegram ? "Бэлэн болмогц Telegram-аар мэдэгдэнэ." : "Тохиргоо хэсэгт Telegram тохируулбал бэлэн болмогц мэдэгдэнэ."}
        {" "}Бэлдэх үед AI хэдэн минут түр зогсоно.
      </p>
      <ActionStatus error={error} />
    </div>
  );
}
