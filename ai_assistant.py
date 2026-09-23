import aiohttp
from config import YC_API_KEY, YC_FOLDER_ID

async def ask_yandex_gpt(context: str, user_query: str) -> str:
    """Отправляет контекст из переписок и вопрос администратора в YandexGPT."""
    if not YC_API_KEY or not YC_FOLDER_ID:
        return "⚠️ Ошибка ИИ-модуля: Не настроены YC_API_KEY или YC_FOLDER_ID в файле .env."

    # Правильный официальный эндпоинт API Yandex Cloud Foundation Models
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    headers = {
        "Authorization": f"Api-Key {YC_API_KEY}",
        "x-folder-id": YC_FOLDER_ID,
        "Content-Type": "application/json"
    }

    payload = {
        "modelUri": f"gpt://{YC_FOLDER_ID}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 2000
        },
        "messages": [
            {
                "role": "system",
                "text": (
                    "Ты — ИИ-аналитик корпоративных переписок Telegram. "
                    "Анализируй предоставленный лог сообщений. Отвечай кратко, чётко и только на основе предоставленного текста. "
                    "Если в логах нет ответа на вопрос — прямо скажи об этом. Ничего не придумывай."
                )
            },
            {
                "role": "user",
                "text": f"Лог сообщений чата:\n{context}\n\nВопрос администратора: {user_query}"
            }
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["result"]["alternatives"][0]["message"]["text"]
                else:
                    error_text = await response.text()
                    return f"Ошибка YandexGPT API (Код {response.status}): {error_text}"
    except Exception as e:
        return f"Не удалось связаться с YandexGPT: {e}"
