"""Check the installed local model; sends only a fictional support example."""

import json
import os
import sys
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with urlopen(f"{BASE_URL}/api/version", timeout=10) as response:
        version = json.load(response)["version"]
    with urlopen(f"{BASE_URL}/api/tags", timeout=10) as response:
        models = json.load(response)["models"]
    if MODEL not in [model["name"] for model in models]:
        raise RuntimeError(f"Model is not downloaded. Run: ollama pull {MODEL}")

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Ты помощник техподдержки интернет-провайдера. Отвечай на русском. Дай ровно три коротких безопасных шага диагностики. Не утверждай, что проверил оборудование или создал заявку. Не советуй сбрасывать роутер к заводским настройкам."},
            {"role": "user", "content": "Wi-Fi подключён, но сайты не открываются. Что проверить?"},
        ],
        "stream": False,
        "think": False,
        "options": {"num_ctx": 4096, "num_predict": 256, "temperature": 0.2},
        "keep_alive": "5m",
    }
    started = time.perf_counter()
    request = Request(f"{BASE_URL}/api/chat", data=json.dumps(body).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    content = result.get("message", {}).get("content", "").strip()
    if not result.get("done") or not content:
        raise RuntimeError("Model did not return a completed, non-empty answer.")
    report = {
        "ollama_version": version,
        "model": MODEL,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "answer": content,
        "done_reason": result.get("done_reason"),
        "output_tokens": result.get("eval_count"),
        "load_seconds": round(result.get("load_duration", 0) / 1_000_000_000, 2),
        "generation_tokens_per_second": round(
            result.get("eval_count", 0) * 1_000_000_000 / max(result.get("eval_duration", 0), 1), 2
        ),
    }
    destination = Path(__file__).resolve().parents[1] / ".local" / "model-check.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        raise SystemExit(f"Local model check failed: {exc}") from None
