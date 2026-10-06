import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { API_URL, SESSION_COOKIE } from "./config";
import type { User } from "./types";

/**
 * Нэвтэрсэн хэрэглэгч — cookie-г backend (/api/me) шалгана. Нэвтрээгүй бол null.
 * cache(): нэг render-т layout, page хоёулаа дуудсан ч backend руу нэг л хүсэлт явна.
 */
export const getUser = cache(async (): Promise<User | null> => {
  const store = await cookies();
  if (!store.has(SESSION_COOKIE)) return null;
  const res = await fetch(`${API_URL}/api/me`, {
    headers: { cookie: store.toString() },
    cache: "no-store",
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`Backend алдаа: ${res.status}`);
  return res.json();
});

/** Хамгаалалттай хуудас бүрийн эхэнд: нэвтрээгүй бол /login руу. */
export async function requireUser(): Promise<User> {
  const user = await getUser();
  if (!user) redirect("/login");
  return user;
}
