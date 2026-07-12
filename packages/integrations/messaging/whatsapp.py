"""WhatsApp Business API dispatcher."""
import httpx


class ConsentRequiredError(Exception):
    pass


class WhatsAppDispatcher:
    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, phone_id: str, token: str):
        self.phone_id = phone_id
        self.token = token
        self.opt_in: set[str] = set()  # a remplacer par vraie DB + preuve opt-in

    def register_opt_in(self, phone: str) -> None:
        self.opt_in.add(phone)

    async def send_text(self, to_phone: str, message: str) -> dict:
        if to_phone not in self.opt_in:
            raise ConsentRequiredError(f"Pas d''opt-in pour {to_phone}")
        url = f"{self.BASE_URL}/{self.phone_id}/messages"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": message[:1024]},
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()

    async def send_with_buttons(
        self, to_phone: str, body: str, buttons: list[str]
    ) -> dict:
        if to_phone not in self.opt_in:
            raise ConsentRequiredError(f"Pas d''opt-in pour {to_phone}")
        if len(buttons) > 3:
            buttons = buttons[:3]
        url = f"{self.BASE_URL}/{self.phone_id}/messages"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:1024]},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"btn_{i}", "title": b[:20]}}
                        for i, b in enumerate(buttons)
                    ]
                },
            },
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()