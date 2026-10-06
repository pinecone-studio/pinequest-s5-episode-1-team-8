"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV, type NavItem } from "@/lib/nav";

export function NavLinks({ isAdmin }: { isAdmin: boolean }) {
  const pathname = usePathname();
  return (
    <nav>
      {NAV.map((group, i) => (
        <div key={group.title ?? i}>
          {group.title && (
            <div className="px-4 pt-[22px] pb-2.5 font-mono text-[11px] leading-none font-medium tracking-[.14em] text-muted uppercase">
              {group.title}
            </div>
          )}
          {group.items
            .filter((item) => !item.adminOnly || isAdmin)
            .map((item) => (
              <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} />
            ))}
        </div>
      ))}
    </nav>
  );
}

// /calls/abc ч "Яриа"-г идэвхтэй болгоно
function isActive(pathname: string, href: string) {
  return pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={`mb-0.5 flex items-center gap-3 rounded-[10px] border-[1.5px] px-3.5 py-2.5 text-base whitespace-nowrap ${
        active ? "border-brand font-bold" : "border-transparent hover:bg-panel-2"
      }`}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round"
        strokeLinejoin="round" className={`size-[19px] shrink-0 ${active ? "text-fg" : "text-muted"}`} aria-hidden>
        {item.icon}
      </svg>
      {item.label}
      {active && <span className="ml-auto size-[7px] rounded-full bg-brand" />}
    </Link>
  );
}
