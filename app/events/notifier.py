from app.events.event_models import AssistantAnnouncement
from app.voice.speaker import speaker
from app.logger import get_logger


logger = get_logger("notifier")


class AssistantNotifier:
    def notify(self, event: AssistantAnnouncement):
        logger.info("[ASSISTANT] %s", event.text)
        print(f"[ASSISTANT] {event.text}")
        speaker.say(event.text)

    def say_random(self, group_name: str):
        logger.info("[VOICE_GROUP] %s", group_name)
        speaker.say_random(group_name)

    def say_random_sync(self, group_name: str):
        logger.info("[VOICE_GROUP_SYNC] %s", group_name)
        speaker.say_random_sync(group_name)

    def say(self, text: str):
        logger.info("[VOICE] %s", text)
        speaker.say(text)

    def say_sync(self, text: str):
        logger.info("[VOICE_SYNC] %s", text)
        speaker.say_sync(text)

    def stop_speaking(self):
        """
        Мгновенно останавливает текущую озвучку ассистента.
        """
        logger.info("[VOICE] stop requested")
        speaker.stop(clear_queue=True)

    def is_speaking(self) -> bool:
        """
        Проверяет, говорит ли ассистент сейчас.
        """
        return speaker.is_speaking()