import "server-only";

import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { API_URL } from "./config";

/** Server component-оос backend-ийн өгөгдөл унших. Хөтчийн cookie-г дамжуулна (нэвтрэлт, байгууллага).
 *  401 -> /login, 404 -> "олдсонгүй" хуудас. */
export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { cookie: (await cookies()).toString() },
    cache: "no-store",
  });
  if (res.status === 401) redirect("/login");
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Backend алдаа: ${res.status} ${path}`);
  return res.json();
}
