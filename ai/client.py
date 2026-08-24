"""Telepost AI Client — Cloudflare Workers AI for moderation and text processing."""
import logging, time, os
from typing import Optional, List, Dict
import httpx
from bot.config import config

logger = logging.getLogger("telepost.ai")

_client: Optional[httpx.AsyncClient] = None
_stats = {"requests": 0, "success": 0, "fail": 0, "last_error": ""}

async def initialize():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)

async def shutdown():
    global _client
    if _client:
        await _client.aclose()
        _client = None

def stats():
    return dict(_stats)

async def call_cf(messages: List[Dict], max_tokens: int = 500, temperature: float = 0.7) -> str:
    """Call Cloudflare Workers AI. Returns content or empty string."""
    if _client is None:
        await initialize()
    if not config.has_cf():
        logger.warning("Cloudflare AI not configured (CF_ACCOUNT_ID/CF_API_TOKEN missing)")
        return ""

    url = f"https://api.cloudflare.com/client/v4/accounts/{config.CF_ACCOUNT_ID}/ai/v1/chat/completions"
    payload = {
        "model": config.CF_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {config.CF_API_TOKEN}",
        "Content-Type": "application/json",
    }

    _stats["requests"] += 1
    try:
        r = await _client.post(url, json=payload, timeout=30.0, headers=headers)
        if r.status_code == 200:
            data = r.json()
            choices = data.get("choices") or []
            if choices:
                content = (choices[0].get("message", {}).get("content", "") or "").strip()
                if content:
                    _stats["success"] += 1
                    return content
            result = data.get("result", {})
            if isinstance(result, dict):
                content = (result.get("response", "") or "").strip()
                if content:
                    _stats["success"] += 1
                    return content
        _stats["fail"] += 1
        _stats["last_error"] = f"CF {r.status_code}: {r.text[:200]}"
        return ""
    except Exception as e:
        _stats["fail"] += 1
        _stats["last_error"] = f"CF: {type(e).__name__}: {e}"
        return ""

async def moderate_text(text: str) -> dict:
    """Check text for spam/fraud/prohibited content. Returns {ok: bool, reason: str}."""
    if not config.has_cf():
        # No AI available — allow everything
        return {"ok": True, "reason": ""}

    messages = [
        {"role": "system", "content": "Ты модератор объявлений. Проверь текст на спам, мошенничество, мат, запрещённые товары (оружие, наркотики). Ответь ТОЛЬКО JSON: {\"ok\": true/false, \"reason\": \"причина если не ok\"}."},
        {"role": "user", "content": text[:1000]}
    ]
    result = await call_cf(messages, max_tokens=100, temperature=0.1)
    if not result:
        return {"ok": True, "reason": ""}

    # Try to parse JSON
    import json
    try:
        # Strip markdown code blocks if present
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(clean)
    except:
        # If not JSON, check for "ok" or "not ok" keywords
        lower = result.lower()
        if '"ok": true' in lower or '"ok":true' in lower:
            return {"ok": True, "reason": ""}
        return {"ok": False, "reason": result[:200]}

async def improve_description(text: str) -> str:
    """Improve ad description using AI (optional, only if CF configured)."""
    if not config.has_cf():
        return text

    messages = [
        {"role": "system", "content": "Улучши описание объявления для маркетплейса. Сделай его привлекательнее, но не добавляй выдуманную информацию. Сохрани язык. Максимум 500 символов."},
        {"role": "user", "content": text[:500]}
    ]
    result = await call_cf(messages, max_tokens=300, temperature=0.5)
    return result if result else text

async def generate_category_suggestion(title: str, description: str) -> str:
    """Suggest a category based on ad title and description."""
    if not config.has_cf():
        return "other"

    categories = "elektronika, avto, nedvizhimost, uslugi, rabota, moda, dom-sad, hobbi, eda"
    messages = [
        {"role": "system", "content": f"Определи категорию объявления из списка: {categories}. Ответь ТОЛЬКО названием категории (одно слово)."},
        {"role": "user", "content": f"Заголовок: {title}\nОписание: {description[:300]}"}
    ]
    result = await call_cf(messages, max_tokens=20, temperature=0.1)
    if result:
        result = result.strip().lower()
        for cat in categories.split(", "):
            if cat in result:
                return cat
    return "other"
