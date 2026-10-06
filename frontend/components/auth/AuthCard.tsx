import type { ReactNode } from "react";
import { Brand } from "@/components/Brand";

/** Нэвтрэх / бүртгүүлэх хуудасны төв карт */
export function AuthCard({ title, sub, footer, children }: {
  title: string;
  sub: string;
  footer: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(600px_360px_at_50%_0%,rgba(95,214,143,.08),transparent_70%)] px-4 py-6">
      <div className="flex w-full max-w-[420px] flex-col gap-4 rounded-2xl border border-line bg-panel px-7 py-8">
        <div className="pb-2">
          <Brand />
        </div>
        <div>
          <h1 className="mb-1 text-[26px] font-extrabold tracking-[-.01em]">{title}</h1>
          <p className="text-sm text-muted">{sub}</p>
        </div>
        {children}
        <p className="text-center text-sm text-muted">{footer}</p>
      </div>
    </main>
  );
}
