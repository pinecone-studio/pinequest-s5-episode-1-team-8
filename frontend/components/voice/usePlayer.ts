"use client";

import { useRef, useState } from "react";

/** Нэг удаад нэг аудио тоглуулна. phone=true -> утсаар сонсогдох чанар (8kHz μ-law, backend ?phone=1) */
export function usePlayer() {
  const current = useRef<HTMLAudioElement | null>(null);
  const [error, setError] = useState("");

  function play(url: string, phone = false) {
    setError("");
    current.current?.pause();
    const audio = new Audio(`${url}?${phone ? "phone=1&" : ""}t=${Date.now()}`);
    current.current = audio;
    void audio.play().catch(() => setError("Аудио алга. Эхлээд «Аудиог шинэчлэх» дарна уу."));
  }

  return { play, error };
}
