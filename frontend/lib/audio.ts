// Хөтөч дээр аудио бэлдэх: микрофоны бичлэг эсвэл ямар ч файл (mp3, m4a, wav ...) -> 24kHz mono 16-bit WAV.
// SIM-TRUNK-ийн scripts/record.py · clean()-тэй ижил: чимээгүйг тайрч, дууны түвшинг тэнцүүлнэ.

const RATE = 24000; // SIM-TRUNK TTS-тэй ижил (backend/routes/recordings.py)
const TARGET_RMS = 0.08; // ~ -22 dBFS
const PAD_START = 0.15;
const PAD_END = 0.25;
const MIN_SEC = 0.3;

/** Аудио (Blob/File) -> цэвэрлэсэн WAV. Дуу сонсогдохгүй бол алдаа. */
export async function toCleanWav(blob: Blob): Promise<{ wav: Blob; seconds: number }> {
  const ctx = new AudioContext();
  let decoded: AudioBuffer;
  try {
    decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
  } catch {
    throw new Error("Аудио файлыг уншиж чадсангүй (mp3, m4a, wav ...)");
  } finally {
    void ctx.close();
  }
  // mono + 24kHz (OfflineAudioContext автоматаар холино, хөрвүүлнэ)
  const offline = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * RATE)), RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const samples = clean((await offline.startRendering()).getChannelData(0));
  if (!samples) throw new Error("Дуу сонсогдсонгүй. Микрофоноо шалгаад дахин бичнэ үү.");
  return { wav: encodeWav(samples), seconds: samples.length / RATE };
}

/** Эхэн, сүүлийн чимээгүйг тайрч (бага зэрэг завсар үлдээнэ), дууны түвшинг тэнцүүлнэ */
export function clean(audio: Float32Array): Float32Array | null {
  if (audio.length < RATE * MIN_SEC) return null;
  const frame = Math.floor(RATE * 0.02);
  const n = Math.floor(audio.length / frame);
  const rms = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let sum = 0;
    for (let j = i * frame; j < (i + 1) * frame; j++) sum += audio[j] * audio[j];
    rms[i] = Math.sqrt(sum / frame);
  }
  const sorted = Array.from(rms).sort((a, b) => a - b);
  const threshold = Math.max(0.01, 0.1 * sorted[Math.floor(0.95 * (n - 1))]);
  const first = rms.findIndex((v) => v > threshold);
  if (first < 0) return null;
  let last = n - 1;
  while (rms[last] <= threshold) last--;
  const start = Math.max(0, first * frame - Math.floor(PAD_START * RATE));
  const end = Math.min(audio.length, (last + 1) * frame + Math.floor(PAD_END * RATE));
  const out = audio.slice(start, end);
  if (out.length < RATE * MIN_SEC) return null;

  let sum = 0;
  let count = 0;
  for (const v of out) if (Math.abs(v) > 0.02) { sum += v * v; count++; }
  const level = count ? Math.sqrt(sum / count) : Math.sqrt(out.reduce((s, v) => s + v * v, 0) / out.length);
  let gain = TARGET_RMS / Math.max(level, 1e-4);
  const peak = out.reduce((m, v) => Math.max(m, Math.abs(v)), 0) * gain;
  if (peak > 0.95) gain *= 0.95 / peak;
  for (let i = 0; i < out.length; i++) out[i] *= gain;
  return out;
}

/** Float32 -> 16-bit PCM WAV */
export function encodeWav(samples: Float32Array): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, s: string) => [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, RATE, true);
  view.setUint32(28, RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((v, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * 0x7fff, true));
  return new Blob([buffer], { type: "audio/wav" });
}

/** Микрофоноор бичих. start() -> stop() бичлэгийн Blob-ийг буцаана. */
export async function startRecording(): Promise<{ stop: () => Promise<Blob> }> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Микрофон зөвхөн localhost эсвэл https хаяг дээр ажиллана. Файлаар оруулж болно.");
  }
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch {
    throw new Error("Микрофон ашиглах зөвшөөрөл өгөөгүй байна (хөтчийн хаягийн мөрөнд зөвшөөрнө)");
  }
  const recorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.start();
  return {
    stop: () =>
      new Promise((resolve) => {
        recorder.onstop = () => {
          stream.getTracks().forEach((track) => track.stop());
          resolve(new Blob(chunks, { type: recorder.mimeType }));
        };
        recorder.stop();
      }),
  };
}
