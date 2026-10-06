import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE } from "@/lib/config";

// Хурдан (optimistic) шалгалт: session cookie огт байхгүй бол хуудсыг зурахгүй, шууд /login руу.
// Cookie жинхэнэ эсэхийг backend шалгана (lib/session.ts -> /api/me).
export function proxy(request: NextRequest) {
  if (!request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // /login, /api (backend руу дамжина), Next-ийн файлууд, icon-оос бусад бүх хуудас
  matcher: ["/((?!login|api|_next/static|_next/image|icon.svg).*)"],
};
