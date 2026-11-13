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
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]  # bağlı kanalın adını göstermek için
CLIENT_SECRET = os.environ.get("KICKCLIP_CLIENT_SECRET", os.path.join(ROOT, "client_secret.json"))
TOKEN_FILE = os.environ.get("KICKCLIP_YT_TOKEN", os.path.join(ROOT, "youtube_token.json"))
CHANNEL_FILE = os.path.join(os.path.dirname(TOKEN_FILE), "youtube_channel.json")
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
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if not set(SCOPES) <= set(creds.scopes or []):
                creds = None  # eski/eksik izinli token -> yeniden izin iste
        except Exception:
            creds = None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None
    if (not creds or not creds.valid) and os.environ.get("CI"):
        raise YouTubeSetupError(
            "Bulutta YouTube bağlantısı geçersiz ya da süresi dolmuş. Bilgisayarında KickClip'te YouTube'u yeniden "
            "bağla, sonra youtube_token.json dosyasının içeriğini GitHub'da YT_TOKEN secret'ına tekrar yapıştır. "
            "(Google Auth Platform -> Kitle -> 'Uygulamayı yayınla' dersen 7 günde bir dolmaz.)")
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


def connect() -> dict:
    """Tarayıcıda Google izni alır, bağlanan kanalı döndürür ve kaydeder."""
    import json
    from googleapiclient.discovery import build
    with _lock:
        creds = _credentials()
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        info = {"title": "(bu hesapta YouTube kanalı yok - önce youtube.com'da kanal oluştur)", "id": None}
    else:
        ch = items[0]
        info = {"title": ch["snippet"]["title"], "id": ch["id"],
                "url": f"https://youtube.com/channel/{ch['id']}"}
    with open(CHANNEL_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)
    return info


def channel() -> dict | None:
    import json
    if not (is_authorized() and os.path.exists(CHANNEL_FILE)):
        return None
    try:
        with open(CHANNEL_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def disconnect() -> None:
    for p in (TOKEN_FILE, CHANNEL_FILE):
        try:
            os.remove(p)
        except OSError:
            pass


def has_client_secret() -> bool:
    return os.path.exists(CLIENT_SECRET)


def upload_short(video_path: str, title: str, description: str = "", tags: Optional[list[str]] = None,
                 privacy: str = "public", publish_at: Optional[str] = None, category_id: str = "20",
                 log: Logger = default_log) -> dict:
    """Shorts yükler. publish_at: RFC3339 (ör. 2026-11-20T18:00:00+03:00) -> zamanlanmış yayın."""
    return upload_video(video_path, title, description, tags, privacy, publish_at, category_id,
                        shorts=True, log=log)


def upload_video(video_path: str, title: str, description: str = "", tags: Optional[list[str]] = None,
                 privacy: str = "public", publish_at: Optional[str] = None, category_id: str = "24",
                 shorts: bool = False, thumbnail: Optional[str] = None, log: Logger = default_log) -> dict:
    """Videoyu yükler; thumbnail verilirse kapak olarak ayarlar."""
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
            "title": ensure_shorts_title(title) if shorts else ((title or "").strip() or "Yayın")[:100],
            "description": description or ("#shorts" if shorts else ""),
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
    url = f"https://youtube.com/shorts/{vid}" if shorts else f"https://youtu.be/{vid}"
    log(f"Yüklendi: {url}")
    result = {"id": vid, "url": url, "privacy": status["privacyStatus"], "publish_at": publish_at}
    if thumbnail and os.path.isfile(thumbnail):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumbnail, mimetype="image/jpeg")).execute()
            log("Kapak fotoğrafı ayarlandı.")
            result["thumbnail_set"] = True
        except HttpError as e:
            msg = e.content.decode("utf-8", "replace") if hasattr(e, "content") else str(e)
            hint = (" Özel kapak için kanalın telefonla doğrulanmış olmalı: youtube.com/verify"
                    if "forbidden" in msg.lower() or "403" in str(e) else "")
            log(f"Kapak ayarlanamadı: {msg[:200]}{hint}")
            result["thumbnail_set"] = False
            result["thumbnail_error"] = msg[:300] + hint
    return result
