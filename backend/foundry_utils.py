import subprocess
import json

DEFAULT_FOUNDRY_PORT = 43456


def discover_foundry_endpoint() -> str:
    """
    'foundry status' çıktısından servisin GÜNCEL adresini okur.

    Foundry Local her yeniden başladığında farklı bir port seçebiliyor, bu yüzden
    sabit bir port'a güvenmek yerine her seferinde CLI'a soruyoruz. Servis kapalıysa
    veya CLI yoksa varsayılan port'a düşer -- çağıran taraf zaten bağlantı hatasını
    kullanıcıya anlamlı bir mesajla bildiriyor.
    """
    try:
        result = subprocess.run(
            ["foundry", "status", "--output", "json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        web_urls = json.loads(result.stdout).get("service", {}).get("webUrls", [])
        if web_urls:
            return web_urls[0].rstrip("/")
    except Exception as e:
        print(f"[Foundry Local] Servis adresi tespit edilemedi: {e}")
    return f"http://127.0.0.1:{DEFAULT_FOUNDRY_PORT}"


def get_chat_completions_url() -> str:
    """Foundry Local'ın OpenAI uyumlu chat completions endpoint'ini döner."""
    return f"{discover_foundry_endpoint()}/v1/chat/completions"


def is_model_loaded(model_alias: str) -> bool:
    """
    'foundry cache ls' çıktısını kontrol ederek modelin Foundry Local
    belleğinde (RAM/GPU) yüklü olup olmadığını döner.
    """
    try:
        result = subprocess.run(
            ["foundry", "cache", "ls", "--output", "json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        data = json.loads(result.stdout)
        for model in data.get("models", []):
            if model.get("alias") == model_alias and model.get("loaded"):
                return True
        return False
    except Exception as e:
        print(f"[Foundry Local] Model durumu kontrol edilemedi: {e}")
        return False


def is_service_running() -> bool:
    try:
        result = subprocess.run(
            ["foundry", "status", "--output", "json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        return json.loads(result.stdout).get("service", {}).get("ready", False)
    except Exception:
        return False


def ensure_service_running():
    """Foundry Local daemon'ı kapalıysa başlatır (düşük RAM'de kendiliğinden kapanabiliyor)."""
    if is_service_running():
        return
    print("[Foundry Local] Servis çalışmıyor, başlatılıyor...")
    try:
        result = subprocess.run(
            ["foundry", "server", "start"],
            capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            print("[Foundry Local] Servis başlatıldı.")
        else:
            print(f"[Foundry Local] Servis başlatılamadı: {result.stderr or result.stdout}")
    except FileNotFoundError:
        print("[Foundry Local] 'foundry' komutu bulunamadı. Foundry Local kurulu mu / PATH'te mi kontrol edin.")
    except Exception as e:
        print(f"[Foundry Local] Servis başlatılırken hata oluştu: {e}")


def ensure_model_loaded(model_alias: str):
    """
    Backend başlarken çağrılır: servisi ve modeli hazır hale getirir. Model zaten
    yüklüyse hiçbir şey yapmaz. Foundry Local kurulu değilse veya başlatılamıyorsa
    hatayı loglar, backend'in ayağa kalkmasını engellemez (README/sohbet
    endpoint'leri kendi fallback'lerini kullanır).
    """
    ensure_service_running()

    if is_model_loaded(model_alias):
        print(f"[Foundry Local] '{model_alias}' zaten belleğe yüklü.")
        return

    print(f"[Foundry Local] '{model_alias}' modeli yükleniyor, bu biraz sürebilir...")
    try:
        result = subprocess.run(
            ["foundry", "model", "load", model_alias],
            capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            print(f"[Foundry Local] '{model_alias}' başarıyla yüklendi.")
        else:
            print(f"[Foundry Local] '{model_alias}' yüklenemedi: {result.stderr or result.stdout}")
    except FileNotFoundError:
        print("[Foundry Local] 'foundry' komutu bulunamadı. Foundry Local kurulu mu / PATH'te mi kontrol edin.")
    except subprocess.TimeoutExpired:
        print(f"[Foundry Local] '{model_alias}' yükleme zaman aşımına uğradı.")
    except Exception as e:
        print(f"[Foundry Local] '{model_alias}' yüklenirken hata oluştu: {e}")
