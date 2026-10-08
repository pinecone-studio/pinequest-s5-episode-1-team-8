"use client";

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/Button";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Устгах",
  cancelLabel = "Цуцлах",
  danger = true,
  pending = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelBtnRef = useRef<HTMLButtonElement>(null);

  // Нээгдэхэд Cancel товч эхэлж focus авна
  useEffect(() => {
    if (open) {
      const timer = setTimeout(() => {
        cancelBtnRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [open]);

  // Escape дарж хаах
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !pending) {
        onCancel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, pending, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-md rounded-[16px] border border-line-2 bg-panel p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-fg">{title}</h3>
        <p className="mt-2 text-sm text-muted leading-relaxed">{description}</p>

        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            ref={cancelBtnRef}
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="inline-flex items-center justify-center rounded-[10px] border border-line-2 bg-bg px-4 py-2 text-sm font-medium text-fg transition-colors hover:bg-line-2/50 focus:outline-none focus:ring-2 focus:ring-brand disabled:opacity-50 cursor-pointer"
          >
            {cancelLabel}
          </button>
          
          <Button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className={`cursor-pointer ${
              danger
                ? "bg-red-600 text-white hover:bg-red-700 focus:ring-red-500"
                : ""
            }`}
          >
            {pending ? "Түр хүлээнэ үү..." : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}