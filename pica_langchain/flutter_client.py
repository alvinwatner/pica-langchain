"""
Flutter UI Pica client for LangChain integration.
"""

from typing import Optional
from .client import PicaClient
from .models import PicaClientOptions
from .logger import get_logger

logger = get_logger()

class FlutterPicaClient(PicaClient):
    """
    Extended Pica client that supports Flutter UI generation.
    
    This client is a thin wrapper around the standard PicaClient that adds
    Flutter UI-specific functionality while reusing all the core capabilities.
    """
    
    def __init__(self, secret: str, options: Optional[PicaClientOptions] = None):
        """
        Initialize the Flutter Pica client.
        
        Args:
            secret: The API secret for Pica.
            options: Optional configuration parameters.
        """
        super().__init__(secret, options)
        logger.info("Initializing Flutter Pica client")
        
    def _generate_system_prompt(self) -> None:
        """
        Override to generate a system prompt that includes Flutter UI generation guidance.
        """
        # First call the parent method to generate the base system prompt
        super()._generate_system_prompt()
        
        # Append Flutter UI specific instructions
        flutter_instructions = """
        
FLUTTER UI GENERATION INSTRUCTIONS:
When processing user requests, remember that your responses will be converted to Flutter UI JSON.
Consider how information should be visually presented to the user in a mobile interface.
Focus on providing structured data that can be easily transformed into UI components.
"""
        
        # Append the Flutter instructions to the existing system prompt
        self._system_prompt += flutter_instructions
        logger.debug("Added Flutter UI generation instructions to system prompt")
