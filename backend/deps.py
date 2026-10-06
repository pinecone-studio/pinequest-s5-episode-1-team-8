"""Хүсэлтийн нэвтэрсэн хэрэглэгч, байгууллага (middleware тогтооно). Route-ууд Depends()-ээр авна."""
from fastapi import Request

from tenant import Tenant


def current_user(request: Request) -> dict:
    return request.state.user


def current_tenant(request: Request) -> Tenant:
    return request.state.tenant
