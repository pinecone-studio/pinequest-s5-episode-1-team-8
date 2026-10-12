import type { ReactNode } from "react";

export type NavItem = {
  href: string;
  label: string;
  icon: ReactNode; // <svg viewBox="0 0 24 24"> доторх хэлбэрүүд
  adminOnly?: boolean;
  badge?: keyof Badges; // цэсний баруун талд тоо (0 бол харагдахгүй)
};

/** Sidebar-ын тоон тэмдэг (backend /api/status-аас, 10с тутам) */
export type Badges = { new_leads: number; unanswered: number };

export const NAV: { title?: string; items: NavItem[] }[] = [
  {
    items: [
      { href: "/", label: "Самбар", icon: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /> },
      { href: "/calls", label: "Ярианууд", icon: <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" /> },
      { href: "/leads", label: "Бүртгэлүүд", badge: "new_leads", icon: <><circle cx="9" cy="8" r="4" /><path d="M2 21v-1a6 6 0 0 1 6-6h2a6 6 0 0 1 6 6v1" /><path d="M19 8v6M16 11h6" /></> },
      { href: "/unanswered", label: "Хариулаагүй асуулт", badge: "unanswered", icon: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7v.5M12 17h.01" /></> },
    ],
  },
  {
    title: "AI туслах",
    items: [
      { href: "/setup", label: "Эхлүүлэх", icon: <><path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" /></> },
      { href: "/knowledge", label: "AI-ийн мэдээлэл", icon: <><path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2z" /><path d="M8 7h6M8 11h6" /></> },
      { href: "/faq", label: "Асуулт, хариулт", icon: <><path d="M4 5h16v11H9l-5 4z" /><path d="M8 9h8M8 12h5" /></> },
      { href: "/voice", label: "Дуу хоолой", icon: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></> },
    ],
  },
  {
    title: "Тусламж",
    items: [
      { href: "/settings", label: "Тохиргоо", icon: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" /></> },
      { href: "/guide", label: "Тусламж", icon: <><path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H11v17H5.5A1.5 1.5 0 0 1 4 18.5z" /><path d="M20 4.5A1.5 1.5 0 0 0 18.5 3H13v17h5.5a1.5 1.5 0 0 0 1.5-1.5z" /></> },
    ],
  },
  {
    title: "Admin",
    items: [
      { href: "/admin", label: "Байгууллагууд", adminOnly: true, icon: <><rect x="3" y="4" width="18" height="6" rx="1" /><rect x="3" y="14" width="18" height="6" rx="1" /></> },
      { href: "/assistant", label: "AI туршилт", adminOnly: true, icon: <><path d="M4 5h16v11H9l-5 4z" /><circle cx="9" cy="10.5" r=".6" /><circle cx="12" cy="10.5" r=".6" /><circle cx="15" cy="10.5" r=".6" /></> },
      { href: "/english", label: "Англи хэл", adminOnly: true, icon: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></> },
      { href: "/train", label: "AI сургалт", adminOnly: true, icon: <><path d="M12 3a4 4 0 0 0-4 4v1a4 4 0 0 0-3 6.5A4 4 0 0 0 9 21h1V3z" /><path d="M12 3a4 4 0 0 1 4 4v1a4 4 0 0 1 3 6.5A4 4 0 0 1 15 21h-1" /></> },
      { href: "/database", label: "Өгөгдлийн сан", adminOnly: true, icon: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></> },
    ],
  },
];

export function findNavItem(href: string): NavItem | undefined {
  return NAV.flatMap((g) => g.items).find((item) => item.href === href);
}
