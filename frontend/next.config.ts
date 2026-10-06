import type { NextConfig } from "next";

// Python backend (backend/app.py). Хөтөч зөвхөн Next.js-тэй ярина: /api/* -> backend руу дамжина,
// тиймээс session cookie нэг домэйн дээр үлдэнэ (CORS хэрэггүй).
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8100";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
