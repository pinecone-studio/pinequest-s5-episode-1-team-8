"use client";

import { useState } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiSend } from "@/lib/client";
import type { OutboundConfig } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const INPUT = "w-full rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2 text-sm focus:border-brand focus:outline-none";

/** Платформын admin: AI аль замаар залгах вэ — GSM gateway / SIP trunk (SIP), iMac+iPhone, унтраах */
export function OutboundSettings({ initial }: { initial: OutboundConfig }) {
  const [cfg, setCfg] = useState(initial);
  const [password, setPassword] = useState("");
  const [check, setCheck] = useState<{ ready: boolean; detail: string } | null>(null);
  const { pending, error, message, run } = useAction();
  const set = (patch: Partial<OutboundConfig>) => setCfg((c) => ({ ...c, ...patch }));

  function save() {
    void run(async () => {
      const r = await apiSend<OutboundConfig>("/api/admin/outbound", "PUT", { ...cfg, password: password || null });
      setCfg(r);
      setPassword("");
      setCheck(await apiSend("/api/admin/outbound/check", "POST"));
    }, "Хадгаллаа ✓");
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="text-sm text-muted">Залгах арга
        <select value={cfg.mode} onChange={(e) => set({ mode: e.target.value as OutboundConfig["mode"] })} className={`${INPUT} mt-1`}>
          <option value="off">Унтраалттай</option>
          <option value="sip">GSM gateway / SIP trunk (SIP)</option>
          <option value="mac">iMac + iPhone (BlackHole, туршилтын)</option>
        </select>
      </label>
      {cfg.mode === "sip" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm text-muted">Хаяг (gateway IP эсвэл SIP сервер)
            <input value={cfg.host ?? ""} onChange={(e) => set({ host: e.target.value })} placeholder="192.168.1.50" className={`${INPUT} mt-1`} /></label>
          <label className="text-sm text-muted">Порт
            <input type="number" value={cfg.port ?? 5060} onChange={(e) => set({ port: Number(e.target.value) })} className={`${INPUT} mt-1`} /></label>
          <label className="text-sm text-muted">Нэвтрэх нэр
            <input value={cfg.user ?? "ai"} onChange={(e) => set({ user: e.target.value })} className={`${INPUT} mt-1`} /></label>
          <label className="text-sm text-muted">Нууц үг {cfg.password_set && "(хадгалагдсан — солих бол шинээр)"}
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" className={`${INPUT} mt-1`} /></label>
          <label className="text-sm text-muted">Дугаарын угтвар (SIP trunk: +976, gateway: хоосон)
            <input value={cfg.prefix ?? ""} onChange={(e) => set({ prefix: e.target.value })} className={`${INPUT} mt-1`} /></label>
          <label className="text-sm text-muted">Энэ компьютерийн IP (хоосон бол автомат)
            <input value={cfg.local_ip ?? ""} onChange={(e) => set({ local_ip: e.target.value })} className={`${INPUT} mt-1`} /></label>
        </div>
      )}
      <p className="text-sm text-muted">
        GSM gateway-г «SIP trunk / IP-ээр дуудлага хүлээн авах» горимд тохируулж энэ компьютерийн IP-г зөвшөөрнө. Залгах цаг 09–20,
        нэг удаад нэг дуудлага. Утсаа аваагүй бол 30 минутын дараа (нийт 3 удаа).
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={save} disabled={pending}>Хадгалаад шалгах</Button>
        {check && <span className={`text-sm ${check.ready ? "text-brand" : "text-danger"}`}>{check.ready ? "✓ " : "✗ "}{check.detail}</span>}
        <ActionStatus error={error} message={message} />
      </div>
    </div>
  );
}
