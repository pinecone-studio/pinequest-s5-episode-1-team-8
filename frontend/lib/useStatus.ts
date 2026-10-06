"use client";

import { useMemo, useSyncExternalStore } from "react";
import type { Status } from "./types";

// AI ресепшний төлөв (/api/status) — sidebar-ын бүх хэсэг НЭГ хүсэлтийг хуваалцана, 10с тутам шинэчилнэ.
const INTERVAL = 10_000;

type Snapshot = { status: Status | null; offline: boolean };
let snapshot: Snapshot | null = null;
const listeners = new Set<() => void>();
let timer: number | undefined;

/** Төлөвийг одоо дахин асууна (жишээ нь бүртгэлийн төлөв солисны дараа тоог шууд шинэчлэх) */
export async function refreshStatus() {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (res.status === 401) return; // гарсан — хуудас өөрөө /login руу шилжинэ
    snapshot = res.ok ? { status: await res.json(), offline: false } : { status: snapshot?.status ?? null, offline: false };
  } catch {
    snapshot = { status: snapshot?.status ?? null, offline: true }; // backend унтарсан
  }
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  if (listeners.size === 1) timer = window.setInterval(refreshStatus, INTERVAL);
  return () => {
    listeners.delete(notify);
    if (!listeners.size) window.clearInterval(timer);
  };
}

/** initial — server талд уншсан анхны төлөв (хуудас ачаалахад шууд харагдана) */
export function useStatus(initial: Status | null): Snapshot {
  const fallback = useMemo(() => ({ status: initial, offline: false }), [initial]); // тогтвортой лавлагаа (React шаардана)
  return useSyncExternalStore(subscribe, () => snapshot ?? fallback, () => fallback);
}
