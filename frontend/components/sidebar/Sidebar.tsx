import Link from "next/link";
import { Brand } from "@/components/Brand";
import type { Badges } from "@/lib/nav";
import type { User } from "@/lib/types";
import { NavLinks } from "./NavLinks";
import { UserCard } from "./UserCard";

export function Sidebar({ user, badges }: { user: User; badges: Badges | null }) {
  return (
    <aside className="sticky top-0 flex h-screen w-[270px] shrink-0 flex-col overflow-y-auto border-r border-line px-[18px] pt-[30px] pb-[18px] max-md:static max-md:h-auto max-md:w-full max-md:border-r-0 max-md:border-b">
      <Link href="/" className="px-3 pb-[30px]">
        <Brand name={user.tenant_name} />
      </Link>
      <NavLinks isAdmin={user.role === "admin"} badges={badges} />
      <div className="mt-auto border-t border-line pt-[18px]">
        <UserCard user={user} />
      </div>
    </aside>
  );
}
