// AI ресепшний тогтмол хаяг: https://sim-trunk.<account>.workers.dev -> iMac дээрх систем (Cloudflare Tunnel).
// Систем өөрөө (Whisper, bge-m3, F5 ~8GB) Worker-т багтахгүй тул iMac дээрээ ажиллана; Worker зөвхөн дамжуулна.
// Quick tunnel-ийн хаяг дахин асах бүрт солигддог -> scripts/tunnel.sh шинэ хаягийг KV-ийн "origin"-д бичнэ.
// PROXY_SECRET: залгагчийн жинхэнэ IP-г (x-client-ip) вэб зөвхөн энэ нууцтай үед итгэнэ (нэвтрэлтийн хязгаарлалт).

const OFFLINE = `<!doctype html><html lang="mn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI ресепшн</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0f17;color:#e6e9ef;
font:16px/1.5 system-ui,sans-serif}div{max-width:420px;padding:24px;text-align:center}
h1{font-size:20px;margin:0 0 8px}p{color:#9aa3b2;margin:0}</style></head>
<body><div><h1>AI ресепшн түр холбогдохгүй байна</h1>
<p>Сервер дахин асаж байж магадгүй. Хэдэн минутын дараа хуудсаа дахин ачаална уу.</p></div></body></html>`;

function offline() {
  return new Response(OFFLINE, { status: 503, headers: { "content-type": "text/html; charset=utf-8", "retry-after": "60" } });
}

export default {
  async fetch(request, env) {
    const origin = await env.ORIGIN.get("origin", { cacheTtl: 60 });
    if (!origin) return offline();
    const url = new URL(request.url);
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.set("x-client-ip", request.headers.get("cf-connecting-ip") || "");
    headers.set("x-proxy-secret", env.PROXY_SECRET || "");
    let res;
    try {
      res = await fetch(new URL(url.pathname + url.search, origin), {
        method: request.method, headers, body: request.body, redirect: "manual",
      });
    } catch {
      return offline();
    }
    if (res.status === 530 || res.status === 502) return offline();     // tunnel унтарсан / хаяг хуучирсан
    const out = new Headers(res.headers);
    const loc = out.get("location");
    if (loc && loc.startsWith(origin)) out.set("location", loc.slice(origin.length) || "/");
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers: out });
  },
};
