import Link from "next/link";
import { TenantSwitch } from "@/components/admin/TenantSwitch";
import { Brand } from "@/components/Brand";
import type { AdminTenant, Status, User } from "@/lib/types";
import { MobileMenu } from "./MobileMenu";
import { NavLinks } from "./NavLinks";
import { UserCard } from "./UserCard";

export function Sidebar({ user, status, tenants }: { user: User; status: Status | null; tenants?: AdminTenant[] | null }) {
  return (
    <aside className="sticky top-0 flex h-screen w-[270px] shrink-0 flex-col overflow-y-auto border-r border-line px-[18px] pt-[30px] pb-[18px] max-md:static max-md:h-auto max-md:w-full max-md:border-r-0 max-md:border-b max-md:py-4">
      <MobileMenu
        header={
          <Link href="/" className="min-w-0">
            <Brand name={user.tenant_name} />
          </Link>
        }
      >
        <NavLinks isAdmin={user.role === "admin"} status={status} />
        <div className="mt-auto border-t border-line pt-[18px] max-md:mt-4">
          <UserCard user={user} status={status} />
          {tenants && tenants.length > 1 && <TenantSwitch tenants={tenants} current={user.tenant} />}
        </div>
      </MobileMenu>
    </aside>
  );
}
