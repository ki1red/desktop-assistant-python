from app.events.event_models import AssistantAnnouncement
from app.voice.speaker import speaker


class AssistantNotifier:
    def notify(self, event: AssistantAnnouncement):
        print(f"[ASSISTANT] {event.text}")
        speaker.say(event.text)

    def say_random(self, group_name: str):
        speaker.say_random(group_name)

    def say_random_sync(self, group_name: str):
        speaker.say_random_sync(group_name)

    def say(self, text: str):
        speaker.say(text)

    def say_sync(self, text: str):
        speaker.say_sync(text)