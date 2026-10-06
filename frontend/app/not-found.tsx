import Link from "next/link";
import { Brand } from "@/components/Brand";

// Байхгүй хаяг, эсвэл харах эрхгүй хуудас (жишээ нь admin биш хүн /admin)
export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <Brand />
      <div className="mt-4 font-mono text-6xl font-extrabold text-brand">404</div>
      <h1 className="text-2xl font-extrabold">Хуудас олдсонгүй</h1>
      <p className="max-w-md text-muted">Хаяг буруу, устсан эсвэл энэ хуудсыг харах эрх танд алга.</p>
      <Link href="/" className="mt-2 rounded-[10px] bg-brand px-5 py-2.5 font-semibold text-[#07130c] hover:bg-brand-2">
        Самбар руу буцах
      </Link>
    </main>
  );
}
