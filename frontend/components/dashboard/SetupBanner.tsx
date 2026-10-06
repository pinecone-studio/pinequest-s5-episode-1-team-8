import Link from "next/link";
import { Card } from "@/components/ui/Card";

/** Мэдээлэл оруулаагүй байгууллагад: "Тохируулах" руу урих */
export function SetupBanner() {
  return (
    <Card className="mb-[34px] border border-brand">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="mb-1.5 text-[15px] font-semibold">AI ресепшнээ тохируулж дуусгаарай</h2>
          <p className="text-muted">Байгууллагын мэдээлэл → мэдээлэл оруулах → бэлдэх. Код бичих шаардлагагүй.</p>
        </div>
        <Link href="/setup" className="rounded-[10px] bg-brand px-[26px] py-[15px] font-semibold text-[#07130c] hover:bg-brand-2">
          Тохируулах →
        </Link>
      </div>
    </Card>
  );
}
