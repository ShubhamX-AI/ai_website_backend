import logging
from livekit.agents import Agent

class BaseAgent(Agent):
    def __init__(self, room, instructions: str) -> None:
        super().__init__(instructions=instructions)
        self.room = room
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def welcome_message(self):
        return "Hello, how can I help you today?"
