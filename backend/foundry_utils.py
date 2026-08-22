import subprocess
import json


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


def ensure_model_loaded(model_alias: str):
    """
    Backend başlarken çağrılır: model zaten yüklüyse hiçbir şey yapmaz,
    değilse 'foundry model load' ile belleğe yükler. Foundry Local kurulu
    değilse veya servis kapalıysa hatayı loglar, backend'in ayağa kalkmasını
    engellemez (README/sohbet endpoint'leri kendi fallback'lerini kullanır).
    """
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
