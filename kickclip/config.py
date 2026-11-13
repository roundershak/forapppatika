"""Tüm ayarlar tek bir dataclass içinde."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ClipConfig:
    # --- Kaynak ---
    source: str = ""                    # Kick linki (canlı / VOD / klip) veya yerel video dosyası
    output_dir: str = "output"
    work_dir: str = "work"
    max_height: int = 1080              # indirilecek en yüksek çözünürlük
    time_range: Optional[str] = None    # "01:00:00-02:30:00" gibi; sadece bu aralığı indir/işle
    live_minutes: float = 30.0          # canlı yayında kaç dakika kaydedilecek
    download: str = "stream"            # stream: indirmeden akıştan oku, sadece klipleri çek | full: tümünü indir

    # --- Klip seçimi ---
    mode: str = "highlights"            # "highlights" (en hareketli anlar) | "split" (sırayla parçala)
    clip_length: float = 30.0           # saniye
    max_clips: int = 10
    lead_ratio: float = 0.65            # highlight anı klibin yüzde kaçında olsun (öncesindeki gerilim)
    ai: bool = True                     # adayları Whisper + Claude ile değerlendir
    selection: str = "viral"            # viral: tüm yayını yazıya dök, Claude önemli/viral anları seçsin
                                        # tepki: sadece ses tepkisi (gülme/bağırma) adaylarını değerlendir (hızlı)
    ai_candidates: int = 0              # değerlendirilecek aday sayısı (0 = klip sayısı x 2.5)
    ai_window: float = 0.0              # aday başına incelenen pencere (sn, 0 = klip süresi x 2, en az 45)
    flex_length: bool = True            # AI klip süresini ±%50 esnetebilsin (olayın tamamını almak için)

    # --- Yerleşim (1080x1920) ---
    width: int = 1080
    height: int = 1920
    cam_ratio: float = 0.40             # üst panelin (kamera) yüksekliği oranı
    cam: str = "auto"                   # auto | top-left | top-right | bottom-left | bottom-right | none | x,y,w,h
    cam_size: float = 0.28              # preset köşe kullanılırsa kameranın kaynak genişliğine oranı
    cam_zoom: float = 3.2               # auto modda: kamera kırpma genişliği = yüz genişliği * zoom
    screen: str = "crop"                # crop (ortadan kırp, dolu) | fit (tamamını sığdır, bulanık arka plan) | x,y,w,h
    screen_zoom: float = 1.0            # crop modunda ekstra zoom (1.0 = paneli tam dolduracak kadar)

    # --- Altyazı ---
    subtitles: bool = True
    whisper_model: str = "small"        # tiny | base | small | medium | large-v3
    language: Optional[str] = "tr"      # None => otomatik algıla
    device: str = "auto"                # auto | cpu | cuda
    font: str = "Montserrat ExtraBold"
    font_size: int = 78
    words_per_line: int = 3
    uppercase: bool = True
    highlight_color: str = "#FFE600"    # konuşulan kelimenin rengi
    sub_position: float = 0.40          # altyazının dikey konumu (0=üst, 1=alt); varsayılan panel sınırı

    # --- YouTube başlığı ---
    titles: bool = True                 # her klip için Shorts başlığı/açıklaması üret
    streamer: Optional[str] = None      # hashtag'ler için yayıncı adı (boşsa linkten alınır)

    # --- Giriş efekti: zil + blur ---
    intro: bool = True
    intro_hold: float = 0.45            # klip başında ne kadar bulanık kalsın (sn)
    intro_fade: float = 0.20            # blur'un kalkma süresi (sn)
    blur_strength: float = 35.0
    bell_file: Optional[str] = None     # kendi zil sesin (wav/mp3). Boşsa sentetik zil üretilir
    bell_volume: float = 0.9

    # --- Çıktı çözünürlüğü ---
    resolution: str = "4k"              # 4k (2160x3840) | 1080p (1080x1920). Yerleşim 1080 tabanlı hesaplanır, sonra büyütülür

    # --- Kodlama ---
    crf: int = 20
    preset: str = "veryfast"
    fps: int = 30

    extra: dict = field(default_factory=dict)

    def out_size(self) -> tuple[int, int]:
        """Son çıktı boyutu (w, h)."""
        if str(self.resolution).lower() in ("4k", "2160", "2160p", "uhd"):
            return 2160, 3840
        return self.width, self.height

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ClipConfig":
        names = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in names})
