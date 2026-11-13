"""YouTube Shorts yükleme (YouTube Data API v3, OAuth).

İlk kullanımda tarayıcı açılır, Google hesabınla izin verirsin; token `youtube_token.json`
dosyasına kaydedilir ve sonraki yüklemelerde tekrar sorulmaz.
Gerekli: Google Cloud Console'dan indirilen OAuth istemci dosyası `client_secret.json`.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from .titles import ensure_shorts_title
from .utils import Logger, default_log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET = os.environ.get("KICKCLIP_CLIENT_SECRET", os.path.join(ROOT, "client_secret.json"))
TOKEN_FILE = os.environ.get("KICKCLIP_YT_TOKEN", os.path.join(ROOT, "youtube_token.json"))
_lock = threading.Lock()


class YouTubeSetupError(RuntimeError):
    pass


def _credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise YouTubeSetupError("Google kütüphaneleri eksik: pip install -r requirements.txt") from e

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if not os.path.exists(CLIENT_SECRET):
            raise YouTubeSetupError(
                f"'{os.path.basename(CLIENT_SECRET)}' bulunamadı. README'deki 'YouTube kurulumu' adımlarını izleyip "
                f"dosyayı şuraya koy: {CLIENT_SECRET}")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True,
                                      authorization_prompt_message="Tarayıcıda YouTube izni ver: {url}",
                                      success_message="İzin verildi, bu sekmeyi kapatabilirsin.")
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def is_authorized() -> bool:
    return os.path.exists(TOKEN_FILE)


def has_client_secret() -> bool:
    return os.path.exists(CLIENT_SECRET)


def upload_short(video_path: str, title: str, description: str = "", tags: Optional[list[str]] = None,
                 privacy: str = "public", publish_at: Optional[str] = None, category_id: str = "20",
                 log: Logger = default_log) -> dict:
    """Videoyu yükler. publish_at: RFC3339 (ör. 2026-11-20T18:00:00+03:00) -> zamanlanmış yayın."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    if privacy not in ("public", "unlisted", "private"):
        raise ValueError("privacy: public | unlisted | private")
    with _lock:  # aynı anda tek OAuth akışı
        creds = _credentials()
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["privacyStatus"] = "private"  # zamanlama için zorunlu
        status["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": ensure_shorts_title(title),
            "description": description or "#shorts",
            "tags": [t for t in (tags or []) if t][:30],
            "categoryId": category_id,  # 20 = Oyun
        },
        "status": status,
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    log(f"YouTube'a yükleniyor: {body['snippet']['title']}")
    resp = None
    try:
        while resp is None:
            st, resp = req.next_chunk()
            if st:
                log(f"Yükleme %{int(st.progress() * 100)}")
    except HttpError as e:
        msg = e.content.decode("utf-8", "replace") if hasattr(e, "content") else str(e)
        if "quotaExceeded" in msg:
            raise RuntimeError("YouTube API günlük kotası doldu (yaklaşık 6 yükleme/gün). Yarın tekrar dene.") from e
        if "uploadLimitExceeded" in msg:
            raise RuntimeError("Kanalın günlük yükleme limiti doldu.") from e
        raise RuntimeError(f"YouTube hatası: {msg[:400]}") from e
    vid = resp["id"]
    url = f"https://youtube.com/shorts/{vid}"
    log(f"Yüklendi: {url}")
    return {"id": vid, "url": url, "privacy": status["privacyStatus"], "publish_at": publish_at}
