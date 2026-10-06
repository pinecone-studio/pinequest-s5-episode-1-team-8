"""
Хэрэглэгчийн бүртгэл (вэб -> Тохиргоо).

  POST /api/account/password {"current", "new"} -> нууц үг солино. Энэ төхөөрөмж нэвтэрсэн хэвээр,
                                                   бусад төхөөрөмжийн нэвтрэлт хүчингүй болно.
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import accounts
import auth
from deps import current_user

router = APIRouter(prefix="/api/account", tags=["account"])


class PasswordBody(BaseModel):
    current: str
    new: str


@router.post("/password")
def change_password(request: Request, body: PasswordBody, user: dict = Depends(current_user)):
    keys = [f"email:{user['email']}"]
    if auth.too_many_fails(keys):
        raise HTTPException(429, "Олон удаа буруу оролдлоо. 10 минутын дараа дахин оролдоно уу.")
    if not accounts.authenticate(user["email"], body.current):
        auth.record_fail(keys)
        time.sleep(auth.FAIL_DELAY)
        raise HTTPException(400, "Одоогийн нууц үг буруу")
    if body.new == body.current:
        raise HTTPException(400, "Шинэ нууц үг хуучнаасаа өөр байх ёстой")
    try:
        accounts.set_password(user["email"], body.new)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # pw_version өссөн -> хуучин cookie-нууд хүчингүй. Энэ төхөөрөмжид шинэ cookie өгнө.
    response = JSONResponse({"ok": True})
    auth.set_session(response, request, accounts.get(user["id"]))
    return response
