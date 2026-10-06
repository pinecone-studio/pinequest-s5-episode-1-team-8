"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/Button";

// Backend (backend/app.py) унтарсан эсвэл алдаа гарсан үед
export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-3xl font-extrabold">Сервертэй холбогдож чадсангүй</h1>
      <p className="max-w-md text-muted">Backend асаалттай эсэхийг шалгаад дахин оролдоно уу.</p>
      <Button variant="primary" onClick={() => retry()}>
        Дахин оролдох
      </Button>
    </main>
  );
}
