"""Agent d''appel vocal IA via Vapi.ai."""
import httpx


class VapiVoiceAgent:
    BASE_URL = "https://api.vapi.ai"

    def __init__(self, api_key: str, phone_number_id: str):
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.phone_number_id = phone_number_id

    async def start_call(self, to_phone: str, system_prompt: str, first_message: str) -> str:
        url = f"{self.BASE_URL}/call/phone"
        payload = {
            "phoneNumberId": self.phone_number_id,
            "customer": {"number": to_phone},
            "assistant": {
                "model": {"provider": "openai", "model": "gpt-4o", "systemMessage": system_prompt},
                "firstMessage": first_message,
                "endCallFunctionEnabled": True,
            },
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            return r.json().get("id", "")