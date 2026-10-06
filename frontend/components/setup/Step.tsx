import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";

/** Тохируулах хуудасны нэг алхам: дугаар (дууссан бол ✓), гарчиг, агуулга */
export function Step({ n, done, title, children }: { n: number; done: boolean; title: string; children: ReactNode }) {
  return (
    <Card className="mb-[18px]">
      <div className="flex items-start gap-4">
        <div
          className={`grid size-[34px] shrink-0 place-items-center rounded-md font-mono text-[15px] font-medium ${
            done ? "bg-brand/12 text-brand" : "bg-panel-2 text-muted"
          }`}
          aria-label={done ? "Дууссан" : `Алхам ${n}`}
        >
          {done ? "✓" : n}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="mb-2.5 text-[15px] font-semibold">{title}</h2>
          {children}
        </div>
      </div>
    </Card>
  );
}
