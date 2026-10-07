"""
Мэдэгдлийн тохиргоо (вэб -> Тохиргоо -> Telegram).

  GET  /api/settings                  -> токен тохируулсан эсэх (токеныг өөрийг нь буцаахгүй), групп
  PUT  /api/settings/telegram         {"token"} эсвэл {"chat_id", "chat_title"} -> хадгална
  GET  /api/settings/telegram/chats   -> ботод сүүлд мессеж бичсэн групп/хүмүүс
  POST /api/settings/telegram/test    -> групп руу тест мессеж
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import notify
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(t: Tenant = Depends(current_tenant)):
    st = notify.load_settings(t)
    token = st.get("telegram_token") or ""
    return {"telegram_token_set": bool(token), "telegram_token_hint": f"…{token[-4:]}" if token else "",
            "telegram_bot": st.get("telegram_bot"), "telegram_chat_id": st.get("telegram_chat_id"),
            "telegram_chat_title": st.get("telegram_chat_title"), "auto_build": bool(st.get("auto_build"))}


class TelegramBody(BaseModel):
    token: str | None = None          # хоосон бол хуучнаараа
    chat_id: int | str | None = None
    chat_title: str | None = None


@router.put("/telegram")
def put_telegram(body: TelegramBody, t: Tenant = Depends(current_tenant)):
    st = notify.load_settings(t)
    if body.token:
        token = body.token.strip()
        try:
            me = notify.telegram("getMe", token)
        except RuntimeError as e:
            raise HTTPException(400, f"Токен буруу: {e}")
        st.update(telegram_token=token, telegram_bot=me.get("username"))
        st.pop("telegram_chat_id", None)          # шинэ бот -> группээ дахин сонгоно
        st.pop("telegram_chat_title", None)
    if body.chat_id is not None:
        if not st.get("telegram_token"):
            raise HTTPException(400, "Эхлээд ботын токеныг оруулна уу")
        st.update(telegram_chat_id=body.chat_id, telegram_chat_title=(body.chat_title or "")[:120])
    notify.save_settings(t, st)
    return get_settings(t)


@router.get("/telegram/chats")
def telegram_chats(t: Tenant = Depends(current_tenant)):
    """Ботыг группт нэмээд тэнд нэг мессеж бичихэд энд гарч ирнэ."""
    token = notify.load_settings(t).get("telegram_token")
    if not token:
        raise HTTPException(400, "Эхлээд ботын токеныг оруулна уу")
    try:
        updates = notify.telegram("getUpdates", token)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    chats = {}
    for u in updates:
        msg = u.get("message") or u.get("my_chat_member") or u.get("channel_post") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
    return [{"id": k, "title": v} for k, v in chats.items()]


@router.post("/telegram/test")
def telegram_test(t: Tenant = Depends(current_tenant)):
    if not notify.send(t, f"✅ {t.config().get('name', '')} AI ресепшн: Telegram мэдэгдэл ажиллаж байна."):
        raise HTTPException(400, "Илгээж чадсангүй — токен, групп сонгосон эсэхээ шалгана уу")
    return {"ok": True}


class AutoBuildBody(BaseModel):
    enabled: bool


@router.put("/auto-build")
def put_auto_build(body: AutoBuildBody, t: Tenant = Depends(current_tenant)):
    """Нэмэлт (SIM-TRUNK-д алга): мэдээлэл, FAQ өөрчлөгдөхөд автоматаар "Бэлдэх" (knowledge_jobs.schedule_build)."""
    st = notify.load_settings(t)
    st["auto_build"] = body.enabled
    notify.save_settings(t, st)
    return {"ok": True, "auto_build": body.enabled}
