// Python backend-ийн хаяг (server талд л ашиглана; хөтөч /api/* -> next.config.ts rewrites)
export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8100";

// backend/auth.py · COOKIE-тэй ижил байх ёстой
export const SESSION_COOKIE = "pc_session";
