from app.events.event_models import AssistantAnnouncement


class AssistantNotifier:
    def notify(self, event: AssistantAnnouncement):
        print(f"[ASSISTANT] {event.text}")