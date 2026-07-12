"""Envoi email via SendGrid."""
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class SendGridEmail:
    def __init__(self, api_key: str, from_email: str, from_name: str = "OmniAgent"):
        self.client = SendGridAPIClient(api_key)
        self.from_email = from_email
        self.from_name = from_name

    def send(self, to_email: str, subject: str, body: str, html: bool = False) -> str:
        message = Mail(
            from_email=(self.from_email, self.from_name),
            to_emails=to_email,
            subject=subject,
            plain_text_content=None if html else body,
            html_content=body if html else None,
        )
        resp = self.client.send(message)
        return resp.headers.get("X-Message-Id", "")