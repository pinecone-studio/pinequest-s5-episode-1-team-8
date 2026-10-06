import type { ReactNode } from "react";

/** Алдааны мессеж (дэлгэц уншигч шууд уншина) */
export function Alert({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-[10px] bg-danger/12 px-3 py-2.5 text-sm text-danger">
      {children}
    </p>
  );
}

/** Үйлдлийн үр дүн: алдаа (улаан) эсвэл амжилт (ногоон). Хоосон бол юу ч харуулахгүй. */
export function ActionStatus({ error, message }: { error?: string; message?: string }) {
  if (error) return <span role="alert" className="text-sm text-danger">{error}</span>;
  if (message) return <span role="status" className="text-sm text-brand">{message}</span>;
  return null;
}
