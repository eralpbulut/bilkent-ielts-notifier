import hashlib
import os
import time
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://prep.bilkent.edu.tr/ielts/"
STATE_FILE = "last_hash.txt"
NTFY_TOPIC = os.environ["NTFY_TOPIC"]

# Geçici internet / sunucu hatalarında otomatik tekrar dene
session = requests.Session()

retry = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)

session.mount("https://", HTTPAdapter(max_retries=retry))

session.headers.update({
    "User-Agent": "Mozilla/5.0 Bilkent-IELTS-Monitor",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})


def get_page_hash():
    # Cache yüzünden eski sayfanın gelme ihtimalini azalt
    response = session.get(
        URL,
        params={"monitor": int(time.time())},
        timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Kullanıcının görmediği ve sık değişebilecek şeyleri çıkar
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Görünen tüm metni karşılaştır
    text = " ".join(soup.stripped_strings)

    if len(text) < 100:
        raise RuntimeError("Sayfa içeriği beklenmedik şekilde boş geldi.")

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def notify():
    response = session.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=(
            "Bilkent IELTS sayfasında değişiklik tespit edildi!\n"
            "https://prep.bilkent.edu.tr/ielts/"
        ).encode("utf-8"),
        headers={
            "Title": "Bilkent IELTS değişti",
            "Priority": "urgent",
            "Tags": "warning"
        },
        timeout=30
    )

    response.raise_for_status()


current_hash = get_page_hash()

# İlk çalıştırma
if not os.path.exists(STATE_FILE):
    with open(STATE_FILE, "w") as f:
        f.write(current_hash)

    print("İlk durum kaydedildi.")
    raise SystemExit(0)


with open(STATE_FILE, "r") as f:
    previous_hash = f.read().strip()


if current_hash == previous_hash:
    print("Değişiklik yok.")
    raise SystemExit(0)


print("DEĞİŞİKLİK TESPİT EDİLDİ")

# Önce bildirim gönder.
# Bu başarısız olursa program burada hata verir ve hash güncellenmez.
notify()

# Bildirim başarıyla gittikten sonra yeni durumu kaydet.
with open(STATE_FILE, "w") as f:
    f.write(current_hash)

print("Bildirim gönderildi ve yeni durum kaydedildi.")
