"""
Voice Announcement System
"""

import pyttsx3
from flask import current_app
import threading
import queue
import time


class VoiceAnnouncer:
    def __init__(self) -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 150)  # speed percentage
        self.engine.setProperty("volume", 0.9)  # volume 0-1
        self.queue = queue.Queue()
        self.active = False
        self.thread = None

    def start(self):
        if not self.active:
            self.active = True
            self.thread = threading.Thread(target=self._process_queue)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        self.active = False
        if self.thread:
            self.thread.join()

    def announce(self, text):
        self.queue.put(text)

    def _process_queue(self):
        while self.active:
            try:
                text = self.queue.get(timeout=1)
                self.engine.say(text)
                self.engine.runAndWait()
                time.sleep(0.5)  # Brief pause between announcements
            except queue.Empty:
                continue


# Global announcer instance
announcer = VoiceAnnouncer()


def init_voice_system(app):
    with app.app_context():
        announcer.start()
        app.logger.info("Voice announcement system started")


def announce(text):
    announcer.announce(text)
