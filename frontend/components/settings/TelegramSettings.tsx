"use client";

import { useState, type FormEvent } from "react";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { apiSend } from "@/lib/client";
import type { Settings } from "@/lib/types";
import { useAction } from "@/lib/useAction";

type Chat = { id: number; title: string };

/** Ботын токен -> групп хайх/сонгох -> тест мессеж */
export function TelegramSettings({ settings }: { settings: Settings }) {
  const { pending, error, message, run } = useAction();
  const [chats, setChats] = useState<Chat[] | null>(null);

  function saveToken(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const token = String(new FormData(form).get("token") ?? "").trim();
    run(async () => {
      const st = await apiSend<Settings>("/api/settings/telegram", "PUT", { token });
      form.reset();
      setChats(null);
      return st;
    }, "Бот холбогдлоо ✓ Одоо группээ сонгоно уу");
  }

  function findChats() {
    run(async () => {
      const list = await apiSend<Chat[]>("/api/settings/telegram/chats", "GET");
      setChats(list);
      if (!list.length) throw new Error("Олдсонгүй. Ботыг группт нэмээд тэнд нэг мессеж бичнэ үү.");
    }, "Группээ сонгоно уу");
  }

  function pickChat(id: string) {
    const chat = chats?.find((c) => String(c.id) === id);
    if (!chat) return;
    run(() => apiSend("/api/settings/telegram", "PUT", { chat_id: chat.id, chat_title: chat.title }), `Сонгогдлоо: ${chat.title} ✓`);
  }

  function sendTest() {
    run(() => apiSend("/api/settings/telegram/test", "POST"), "Илгээлээ ✓ Telegram-аа шалгана уу");
  }

  return (
    <div className="flex flex-col gap-5">
      <ol className="list-decimal space-y-1 pl-5 leading-relaxed text-muted">
        <li>Telegram дээр <b className="text-fg">@BotFather</b> → <code className="font-mono text-[13px] text-brand">/newbot</code> → нэр өгөөд <b className="text-fg">токен</b>-г хуулна</li>
        <li>Токеныг доор оруулаад <b className="text-fg">Хадгалах</b></li>
        <li>Ботыг ажилтнуудын <b className="text-fg">группт нэмээд</b>, группт ямар нэг мессеж бичнэ</li>
        <li><b className="text-fg">Групп хайх</b> → группээ сонгоно → <b className="text-fg">Тест мессеж</b></li>
      </ol>

      <form onSubmit={saveToken} className="flex flex-wrap items-end gap-3">
        <div className="min-w-[260px] flex-1">
          <Field
            label={settings.telegram_token_set ? `Ботын токен (хадгалагдсан ${settings.telegram_token_hint} — солих бол шинээр оруулна)` : "Ботын токен"}
            name="token" type="password" placeholder="123456789:ABC-DEF..." required autoComplete="off"
          />
        </div>
        <Button type="submit" variant="primary" disabled={pending}>Хадгалах</Button>
      </form>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" onClick={findChats} disabled={pending || !settings.telegram_token_set}>Групп хайх</Button>
        {chats && chats.length > 0 && (
          <select
            aria-label="Мэдэгдэл очих групп"
            defaultValue=""
            onChange={(e) => pickChat(e.target.value)}
            className="max-w-[420px] flex-1 rounded-[10px] border-[1.5px] border-line-2 bg-bg px-3 py-2.5 text-sm focus:border-brand focus:outline-none"
          >
            <option value="" disabled>— групп сонгоно уу —</option>
            {chats.map((c) => (
              <option key={c.id} value={c.id}>{c.title} ({c.id})</option>
            ))}
          </select>
        )}
        <Button type="button" onClick={sendTest} disabled={pending || !settings.telegram_chat_id}>Тест мессеж</Button>
      </div>

      <div className="min-h-5">
        <ActionStatus error={error} message={message} />
      </div>
    </div>
  );
}
