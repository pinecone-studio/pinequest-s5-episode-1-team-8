"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import { useAction } from "@/lib/useAction";

/** Ажилтны код: багш утсаар "Ажилтны горим" гэж хэлээд энэ кодыг бичвэл бусдын бүртгэлийг утсаар өөрчилнө */
export function StaffPin({ initial }: { initial: string }) {
  const [pin, setPin] = useState(initial);
  const [shown, setShown] = useState(false);
  const { pending, error, message, run } = useAction();
  const regenerate = () =>
    run(async () => {
      const r = await apiSend<{ staff_pin: string }>("/api/people/staff-pin", "POST");
      setPin(r.staff_pin);
      setShown(true);
    }, "Шинэ код үүслээ — хуучин нь хүчингүй");

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
      <div>
        <div className="text-[13px] uppercase tracking-wider text-muted">Ажилтны код</div>
        <button type="button" onClick={() => setShown(!shown)} className="font-mono text-2xl tracking-[0.3em]" title="Харах/нуух">
          {shown ? pin : "••••••"}
        </button>
      </div>
      <p className="max-w-[560px] flex-1 text-sm leading-6 text-muted">
        Багш, ажилтан утсаар залгаад <b className="text-fg">«Ажилтны горим»</b> гэж хэлээд энэ кодыг бичнэ. Дараа нь
        <b className="text-fg"> «Болдын цагийг Баасан гараг руу шилжүүл»</b> гэх мэтээр хэлэхэд AI бүх бүртгэлээс хайж
        олоод өөрчилнө — өгөгдлийн сан руу гараар орох шаардлагагүй.
      </p>
      <div>
        <Button onClick={regenerate} disabled={pending} variant="ghost">Шинэ код</Button>
        <div className="mt-1 min-h-5"><ActionStatus error={error} message={message} /></div>
      </div>
    </div>
  );
}
