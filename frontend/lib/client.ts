// Хөтөч талаас backend руу (/api/* -> next.config.ts rewrites). Client component-уудад.

export const OFFLINE = "Сервертэй холбогдож чадсангүй. Түр хүлээгээд дахин оролдоно уу.";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

/** JSON эсвэл FormData илгээгээд хариуг буцаана. Алдаа бол ApiError (backend-ийн detail мессежтэй).
 *  Session дууссан (401) бол /login руу шилжинэ. */
export async function apiSend<T = unknown>(path: string, method = "POST", body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: body === undefined || isForm ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(OFFLINE, 0);
  }
  const data = await res.json().catch(() => null);
  if (res.status === 401 && !path.startsWith("/api/login")) {
    window.location.assign(new URL("/login", window.location.origin)); // бүрэн ачаалал: хуучин төлөв үлдэхгүй
  }
  if (!res.ok) throw new ApiError(data?.detail ?? OFFLINE, res.status);
  return data as T;
}
