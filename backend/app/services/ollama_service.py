import httpx
from app.config import settings

async def check_ollama() -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            payload = response.json()
            names = [m.get("name", "") for m in payload.get("models", [])]
            matching = any(n == settings.ollama_model or n.startswith(settings.ollama_model + ":") for n in names)
            if matching:
                return True, f"{settings.ollama_model} is available"
            return False, f"Ollama is running, but {settings.ollama_model} is not pulled"
    except (httpx.HTTPError, ValueError):
        return False, "Ollama is not reachable; start Ollama and pull the configured model"

async def generate(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are ApplyAI, a careful job-application assistant. "
                            "Never invent personal facts. If information is missing, say so "
                            "and ask the user. Keep answers concise."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
