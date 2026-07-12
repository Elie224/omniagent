"""Notification Agent : envoie des notifications multi-canal."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any


class NotificationChannel(str, Enum):
    EMAIL = "email"
    PUSH = "push"
    SLACK = "slack"
    IN_APP = "in_app"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    user_id: str
    channel: NotificationChannel
    title: str
    body: str
    priority: Priority = Priority.NORMAL
    metadata: dict | None = None


class NotificationAgent:
    """Dispatche les notifications vers les bons canaux.

    - email/SMS/WhatsApp : via le ConnectorManager
    - push/in_app : via une queue interne (a brancher sur Firebase / WebSocket)
    - slack : webhook (a brancher)
    """

    def __init__(self, history_limit: int = 200):
        self._history: list[Notification] = []
        self._history_limit = history_limit

    def send(self, notif: Notification) -> dict:
        self._history.append(notif)
        if len(self._history) > self._history_limit:
            self._history.pop(0)
        # En prod : routing reel vers les connecteurs
        if notif.channel == NotificationChannel.EMAIL:
            return self._send_email(notif)
        if notif.channel == NotificationChannel.SMS:
            return self._send_sms(notif)
        if notif.channel == NotificationChannel.WHATSAPP:
            return self._send_whatsapp(notif)
        if notif.channel == NotificationChannel.PUSH:
            return self._send_push(notif)
        if notif.channel == NotificationChannel.SLACK:
            return self._send_slack(notif)
        return {"channel": "in_app", "queued": True, "title": notif.title}

    def notify(self, user_id: str, title: str, body: str,
               channel: NotificationChannel = NotificationChannel.IN_APP,
               priority: Priority = Priority.NORMAL,
               metadata: dict | None = None) -> dict:
        return self.send(Notification(user_id, channel, title, body, priority, metadata))

    def notify_bulk(self, user_ids: list[str], title: str, body: str,
                    channel: NotificationChannel = NotificationChannel.IN_APP) -> list[dict]:
        return [self.notify(u, title, body, channel) for u in user_ids]

    def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        return [
            {"channel": n.channel.value, "title": n.title, "body": n.body,
             "priority": n.priority.value, "ts": getattr(n, "_ts", None)}
            for n in self._history[-limit:]
            if n.user_id == user_id
        ]

    # --- Stubs de routage (delegues au ConnectorManager en prod) ---
    def _send_email(self, n: Notification) -> dict:
        return {"channel": "email", "status": "queued", "title": n.title}

    def _send_sms(self, n: Notification) -> dict:
        return {"channel": "sms", "status": "queued", "title": n.title}

    def _send_whatsapp(self, n: Notification) -> dict:
        return {"channel": "whatsapp", "status": "queued", "title": n.title}

    def _send_push(self, n: Notification) -> dict:
        return {"channel": "push", "status": "queued", "title": n.title}

    def _send_slack(self, n: Notification) -> dict:
        return {"channel": "slack", "status": "queued", "title": n.title}


_notification_agent: NotificationAgent | None = None


def get_notification_agent() -> NotificationAgent:
    global _notification_agent
    if _notification_agent is None:
        _notification_agent = NotificationAgent()
    return _notification_agent


async def run(input_data: dict, user_id: str) -> dict:
    action = input_data.get("action", "send")
    agent = get_notification_agent()
    if action == "send":
        return agent.notify(
            user_id=user_id,
            title=input_data["title"],
            body=input_data["body"],
            channel=NotificationChannel(input_data.get("channel", "in_app")),
            priority=Priority(input_data.get("priority", "normal")),
            metadata=input_data.get("metadata"),
        )
    if action == "bulk":
        return {"results": agent.notify_bulk(
            input_data["user_ids"], input_data["title"], input_data["body"],
            NotificationChannel(input_data.get("channel", "in_app")),
        )}
    if action == "history":
        return {"history": agent.get_history(user_id, input_data.get("limit", 20))}
    return {"error": "unknown action"}
