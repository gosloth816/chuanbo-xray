"""Bound inputs and expensive operations in the public studio."""
import base64
import binascii
from collections import deque
from io import BytesIO
from threading import Lock
from time import monotonic

import streamlit as st
from PIL import Image, UnidentifiedImageError

from .constants import is_public_deployment
from .studio_model import StudioError

PHOTO_TYPES = {"data:image/jpeg;base64": "JPEG", "data:image/png;base64": "PNG",
               "data:image/webp;base64": "WEBP"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024
# Limit each browser session and the whole process, including anonymous visitors.
LIMITS = {"model": (300, 12, 90), "account": (300, 15, 120), "captcha": (60, 20, 180),
          "share": (600, 12, 120), "product": (300, 30, 240), "review": (300, 20, 120)}


def bounded_text(value, limit):
    if not isinstance(value, str):
        raise StudioError("请检查提交的文字资料格式。")
    return value[:limit].strip()


def decode_photo(value):
    if value == "":
        return None
    if not isinstance(value, str) or len(value) > 14 * 1024 * 1024:
        raise StudioError("请选择 10 MB 以内的 JPG、PNG 或 WEBP 图片。")
    header, _, encoded = value.partition(",")
    if header not in PHOTO_TYPES or not encoded:
        raise StudioError("请选择 10 MB 以内的 JPG、PNG 或 WEBP 图片。")
    try:
        data = base64.b64decode(encoded, validate=True)
        if not data or len(data) > MAX_PHOTO_BYTES:
            raise StudioError("图片为空或超过 10 MB。")
        with Image.open(BytesIO(data), formats=[PHOTO_TYPES[header]]) as photo:
            if photo.width * photo.height > 24_000_000:
                raise StudioError("图片像素过大，请缩小后重试。")
            photo.verify()
    except (binascii.Error, UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise StudioError("无法读取这张图片，请检查图片格式后重试。") from exc
    return data


@st.cache_resource
def _site_limits():
    return Lock(), {name: deque() for name in LIMITS}


def reserve_request(group):
    if not is_public_deployment():
        return
    seconds, session_limit, site_limit = LIMITS[group]
    now = monotonic()
    sessions = st.session_state.setdefault("studio_limits", {})
    personal = [stamp for stamp in sessions.get(group, ()) if stamp > now - seconds]
    lock, site = _site_limits()
    with lock:
        recent = site[group]
        while recent and recent[0] <= now - seconds:
            recent.popleft()
        if len(personal) >= session_limit or len(recent) >= site_limit:
            raise StudioError("操作过于频繁，请稍后再试。")
        recent.append(now)
    sessions[group] = [*personal, now]
