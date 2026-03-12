from livekit.agents import function_tool, RunContext


class EndCallToolsMixin:
    """Tool for gracefully ending the call and disconnecting from the room."""

    @function_tool
    async def end_call(
        self,
        context: RunContext,
    ):
        """
        Gracefully ends the call and disconnects from the room.
        
        Use this tool when:
        - The user expresses a desire to end the conversation (e.g., "goodbye", "that's all", "hang up").
        - The service or inquiry is complete and no further assistance is needed.
        
        This will shut down the session and disconnect all participants.
        """
        self.logger.info("Ending the call as requested.")
        
        # Shut down the session
        context.session.shutdown()
        
        return "Say exactly this -> Thanks for visiting IndusNet. Bye!"
