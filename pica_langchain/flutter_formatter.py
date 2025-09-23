"""
Flutter UI formatter for converting agent responses to Flutter UI JSON.
"""

import json
from typing import Any, Dict, List, Optional, Union
from langchain.schema import AgentAction, AgentFinish
from langchain.callbacks.manager import CallbackManagerForChainRun
from langchain.chat_models.base import BaseChatModel
from .logger import get_logger

logger = get_logger()


class FlutterUIFormatter:
    """
    Formatter for converting agent responses to Flutter UI JSON.

    This class takes the output from a LangChain agent and uses a fine-tuned
    OpenAI model to convert it into a Flutter server-driven UI JSON format.
    """

    def __init__(
        self, flutter_llm: BaseChatModel, ui_formatter_prompt: Optional[str] = None
    ):
        """
        Initialize the Flutter UI formatter.

        Args:
            flutter_llm: The fine-tuned OpenAI model to use for generating Flutter UI JSON.
            ui_formatter_prompt: Optional custom prompt template for generating Flutter UI JSON.
                                 If provided, it will replace the default prompt template.
                                 The template should include placeholders for {agent_output} and {tool_usage_str}.
        """
        self.flutter_llm = flutter_llm
        self.ui_formatter_prompt = ui_formatter_prompt

    def format_to_ui(
        self,
        user_input: str,
        agent_output: str,
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        """
        Format the agent output to Flutter UI JSON.

        Args:
            user_input: The original user question/request.
            agent_output: The text output from the agent.
            run_manager: Optional callback manager for the chain run.

        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        logger.info("Converting agent output to Flutter UI JSON")

        # Create the messages format
        messages = {
            "messages": [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": agent_output},
            ]
        }

        # Create a prompt for the fine-tuned model
        prompt = self._create_ui_generation_prompt(messages)

        # Generate Flutter UI JSON using the fine-tuned model
        try:
            response = self.flutter_llm.predict(prompt)
            ui_json = self._extract_json(response)
            logger.info("Successfully generated Flutter UI JSON")
            return ui_json
        except Exception as e:
            logger.error(f"Error generating Flutter UI JSON: {e}", exc_info=True)
            # Fallback to a simple UI representation
            return self._create_fallback_ui(str(e))

    def _create_ui_generation_prompt(self, messages: Dict[str, Any]) -> str:
        """
        Create a prompt for the fine-tuned model to generate Flutter UI JSON.

        Args:
            messages: The conversation messages in the specified format.

        Returns:
            A prompt string for the fine-tuned model.
        """
        # Convert messages to JSON string for the prompt
        messages_str = json.dumps(messages, indent=2)

        # Use custom prompt if provided, otherwise use the improved default
        if self.ui_formatter_prompt:
            return f"{self.ui_formatter_prompt}\n\nCONVERSATION:\n{messages_str}"
        else:
            # Default prompt that emphasizes the context-aware approach
            return f"""
You are an AI Assistant specialized in generating Stac JSON for Flutter's Server-Driven UI framework. Your task is to transform conversational exchanges between a user and an AI assistant into properly formatted Stac JSON that creates elegant, intuitive UIs.

CONVERSATION:
{messages_str}

CORE MISSION:
Create a UI that visually presents the assistant's response in a way that directly serves the user's original request. Always consider:
1. What did the user ask for?
2. What type of data did the assistant provide?
3. How can I best visualize this to fulfill the user's intent?

MANDATORY STRUCTURE:
- Root element MUST be "type": "singleChildScrollView"
- Include "padding": {{"left": 16, "right": 16, "top": 16, "bottom": 16}}
- Direct child MUST be "type": "column" with "crossAxisAlignment": "stretch"

DESIGN SYSTEM:
- Containers: color: "white12" or "grey12", borderRadius: 8, border: {{"color": "#848484", "width": 1}}
- Text Headers: "fontWeight": "w600", "color": "#FFFFFF"
- Body Text: {{"color": "#FFFFFF", "fontSize": 12-14}}
- Spacing: {{"type": "sizedBox", "height": 8-20}} between sections

Return ONLY valid JSON - no explanations, no markdown, no code formatting.
"""

    def _extract_json(self, response: str) -> Dict[str, Any]:
        """
        Extract JSON from the model response.

        Args:
            response: The response from the fine-tuned model.

        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        # Try to extract JSON from the response
        try:
            # First, try to parse the entire response as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the response
            try:
                # Look for JSON between triple backticks
                return self._sanitize_json_response(response)
            except Exception as e:
                return self._create_fallback_ui(f"Error extracting JSON: {e}")

    def _extract_user_input(self, inputs: Any) -> str:
        """
        Extract the user's original input from the inputs parameter.

        Args:
            inputs: The inputs passed to the agent.

        Returns:
            The user's original input as a string.
        """
        if isinstance(inputs, dict):
            # Try common keys for user input
            for key in ["input", "query", "question", "user_input", "text"]:
                if key in inputs:
                    return str(inputs[key])
            # If no standard key found, try to find the first string value
            for value in inputs.values():
                if isinstance(value, str):
                    return value
        elif isinstance(inputs, str):
            return inputs

        # Fallback
        return str(inputs)

    def _create_fallback_ui(self, error: str) -> Dict[str, Any]:
        """
        Create a fallback UI when JSON generation fails.

        Args:
            error: The error message.

        Returns:
            A dictionary containing a simple Flutter UI JSON.
        """
        logger.warning(f"Using fallback UI due to error: {error}")

        return {
            "type": "singleChildScrollView",
            "padding": {"left": 16, "right": 16, "top": 16, "bottom": 16},
            "child": {
                "type": "column",
                "crossAxisAlignment": "stretch",
                "children": [
                    {"type": "sizedBox", "height": 20},
                    {
                        "type": "container",
                        "padding": {"left": 16, "right": 16, "top": 24, "bottom": 24},
                        "decoration": {
                            "color": "white12",
                            "borderRadius": 8,
                            "border": {"color": "#848484", "width": 1},
                        },
                        "child": {
                            "type": "column",
                            "crossAxisAlignment": "center",
                            "children": [
                                {"type": "sizedBox", "height": 20},
                                {
                                    "type": "image",
                                    "image": {
                                        "type": "networkImage",
                                        "src": "https://cdn-icons-png.flaticon.com/512/564/564619.png",
                                    },
                                    "width": 64,
                                    "height": 64,
                                },
                                {"type": "sizedBox", "height": 20},
                                {
                                    "type": "text",
                                    "data": "Oops! Something went wrong",
                                    "style": {
                                        "fontWeight": "w600",
                                        "color": "#FFFFFF",
                                        "fontSize": 18,
                                    },
                                    "textAlign": "center",
                                    "overflow": "ellipsis",
                                    "maxLines": 2,
                                },
                                {"type": "sizedBox", "height": 8},
                                {
                                    "type": "text",
                                    "data": "We encountered an unexpected error while rendering the interface. Please try again or contact support if the issue persists.",
                                    "style": {"color": "#FFFFFF", "fontSize": 14},
                                    "textAlign": "center",
                                    "overflow": "ellipsis",
                                    "maxLines": 3,
                                },
                                {"type": "sizedBox", "height": 20},
                            ],
                        },
                    },
                    {"type": "sizedBox", "height": 20},
                ],
            },
        }


    def _sanitize_json_response(self, response: str) -> str:
        """
        Sanitize LLM response to extract valid JSON content.

        This function handles cases where the LLM includes opening messages or other text
        before or after the actual JSON content.

        Args:
            response: The raw LLM response string that should contain JSON

        Returns:
            A cleaned string containing only valid JSON

        Raises:
            ValueError: If no valid JSON can be extracted from the response
        """
        # First attempt: Try to parse the entire response as JSON
        try:
            json.loads(response)
            return response  # If it's already valid JSON, return as is
        except json.JSONDecodeError:
            pass

        # Second attempt: Find JSON array/object pattern using regex
        json_patterns = [
            # Match JSON arrays starting with [ and ending with ]
            r"(\[[\s\S]*\])",
            # Match JSON objects starting with { and ending with }
            r"(\{[\s\S]*\})",
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, response)
            for potential_json in matches:
                try:
                    # Verify this is valid JSON by parsing it
                    json.loads(potential_json)
                    return potential_json
                except json.JSONDecodeError:
                    continue

        # Third attempt: Try to find the first [ or { and last ] or }
        first_bracket = min(
            (response.find("["), response.find("{")), key=lambda x: float("inf") if x == -1 else x
        )
        if first_bracket != -1:
            last_square_bracket = response.rfind("]")
            last_curly_bracket = response.rfind("}")

            # Determine which closing bracket to use based on the opening bracket
            if response[first_bracket] == "[" and last_square_bracket != -1:
                potential_json = response[first_bracket : last_square_bracket + 1]
            elif response[first_bracket] == "{" and last_curly_bracket != -1:
                potential_json = response[first_bracket : last_curly_bracket + 1]
            else:
                raise ValueError("Could not extract valid JSON from the response")

            try:
                # Verify this is valid JSON
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                pass

        # If all attempts fail, raise an error
        raise ValueError("Could not extract valid JSON from the response")

