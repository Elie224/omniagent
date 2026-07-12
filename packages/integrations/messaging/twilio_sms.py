"""Envoi SMS via Twilio."""
from twilio.rest import Client


class TwilioSMS:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number

    def send(self, to_phone: str, body: str) -> str:
        msg = self.client.messages.create(
            body=body[:1600], from_=self.from_number, to=to_phone
        )
        return msg.sid