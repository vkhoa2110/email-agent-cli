import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AuthenticationError, OpenAI

from prompts import SYSTEM_PROMPT
from tools import TOOLS, TOOL_REGISTRY

load_dotenv()


def _get_provider_name(provider: Optional[str] = None) -> str:
    raw_provider = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    aliases = {
        "openai": "openai",
        "gemini": "gemini",
        "google": "gemini",
    }
    normalized = aliases.get(raw_provider)
    if normalized is None:
        raise RuntimeError("LLM_PROVIDER không hợp lệ. Chỉ dùng 'openai' hoặc 'gemini'.")
    return normalized


def _get_required_env(var_name: str, placeholder: str) -> str:
    value = os.getenv(var_name, "").strip()
    if not value or value == placeholder:
        raise RuntimeError(
            f"Thiếu {var_name} hợp lệ. Hãy tạo file .env từ .env.example và điền API key thật trước khi chạy app."
        )
    return value


def _get_gemini_api_key() -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()

    if gemini_api_key and gemini_api_key != "your_gemini_api_key_here":
        return gemini_api_key
    if google_api_key and google_api_key != "your_gemini_api_key_here":
        return google_api_key

    raise RuntimeError(
        "Thiếu GEMINI_API_KEY hoặc GOOGLE_API_KEY hợp lệ. Hãy tạo file .env từ .env.example và điền API key thật trước khi chạy app."
    )


class OpenAIEmailBackend:
    provider_name = "openai"

    def __init__(self, model: Optional[str] = None, max_tool_rounds: int = 5) -> None:
        self.client = OpenAI(
            api_key=_get_required_env("OPENAI_API_KEY", "your_openai_api_key_here")
        )
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4")
        self.max_tool_rounds = max_tool_rounds
        self.previous_response_id: Optional[str] = None

    def _create_response(self, user_input: Any, previous_response_id: Optional[str]) -> Any:
        try:
            return self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=user_input,
                previous_response_id=previous_response_id,
                tools=TOOLS,
                tool_choice="auto",
            )
        except AuthenticationError as exc:
            raise RuntimeError(
                "OPENAI_API_KEY không hợp lệ hoặc đã hết hiệu lực. Cập nhật file .env với API key đúng rồi chạy lại."
            ) from exc

    @staticmethod
    def _extract_function_calls(response: Any) -> List[Any]:
        output = getattr(response, "output", []) or []
        return [item for item in output if getattr(item, "type", None) == "function_call"]

    @staticmethod
    def _safe_output_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text

        texts: List[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "output_text":
                    text = getattr(content, "text", None)
                    if text:
                        texts.append(text)
        return "\n".join(texts).strip()

    def run_turn(self, user_input: str) -> Dict[str, Any]:
        response = self._create_response(
            user_input=user_input,
            previous_response_id=self.previous_response_id,
        )

        tool_rounds = 0
        used_tools = False
        while True:
            function_calls = self._extract_function_calls(response)
            if not function_calls:
                self.previous_response_id = getattr(response, "id", None)
                return {
                    "response_id": getattr(response, "id", None),
                    "text": self._safe_output_text(response),
                    "used_tools": used_tools,
                }

            tool_rounds += 1
            used_tools = True
            if tool_rounds > self.max_tool_rounds:
                self.previous_response_id = getattr(response, "id", None)
                return {
                    "response_id": getattr(response, "id", None),
                    "text": "Agent đã chạm giới hạn số vòng gọi tool. Hãy thử yêu cầu ngắn gọn hơn.",
                    "used_tools": True,
                }

            tool_outputs = []
            for call in function_calls:
                tool_name = getattr(call, "name", "")
                raw_args = getattr(call, "arguments", "{}")
                call_id = getattr(call, "call_id", None)

                try:
                    tool_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    result = {"error": f"Tool arguments không hợp lệ: {raw_args}"}
                else:
                    tool = TOOL_REGISTRY.get(tool_name)
                    if tool is None:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    else:
                        try:
                            result = tool(**tool_args)
                        except Exception as exc:  # pragma: no cover
                            result = {"error": str(exc)}

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            response = self._create_response(
                user_input=tool_outputs,
                previous_response_id=getattr(response, "id", None),
            )

    def reset(self) -> None:
        self.previous_response_id = None


class GeminiEmailBackend:
    provider_name = "gemini"

    def __init__(self, model: Optional[str] = None, max_tool_rounds: int = 5) -> None:
        try:
            from google import genai
            from google.genai import errors, types
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu dependency google-genai. Hãy chạy pip install -r requirements.txt."
            ) from exc

        self._types = types
        self._client_error_cls = errors.ClientError
        gemini_api_key = _get_gemini_api_key()
        original_google_api_key = os.environ.get("GOOGLE_API_KEY")
        if os.environ.get("GEMINI_API_KEY") and original_google_api_key:
            os.environ["GOOGLE_API_KEY"] = ""
        try:
            self.client = genai.Client(api_key=gemini_api_key)
        finally:
            if original_google_api_key is None:
                os.environ.pop("GOOGLE_API_KEY", None)
            else:
                os.environ["GOOGLE_API_KEY"] = original_google_api_key
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.max_tool_rounds = max_tool_rounds
        self.history: List[Any] = []
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool["name"],
                            description=tool.get("description", ""),
                            parameters_json_schema=tool["parameters"],
                        )
                        for tool in TOOLS
                        if tool.get("type") == "function"
                    ]
                )
            ],
        )

    def _create_response(self) -> Any:
        try:
            return self.client.models.generate_content(
                model=self.model,
                contents=self.history,
                config=self.config,
            )
        except self._client_error_cls as exc:
            message = str(exc)
            if "API key" in message or "API_KEY" in message:
                raise RuntimeError(
                    "GEMINI_API_KEY hoặc GOOGLE_API_KEY không hợp lệ hoặc đã hết hiệu lực. Cập nhật file .env với API key đúng rồi chạy lại."
                ) from exc
            raise RuntimeError(f"Gemini API lỗi: {message}") from exc

    @staticmethod
    def _first_candidate_content(response: Any) -> Optional[Any]:
        candidates = getattr(response, "candidates", []) or []
        if not candidates:
            return None
        return getattr(candidates[0], "content", None)

    @staticmethod
    def _safe_output_text(response: Any) -> str:
        try:
            output_text = response.text
        except Exception:
            output_text = None

        if output_text:
            return output_text.strip()

        texts: List[str] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                text = getattr(part, "text", None)
                if text:
                    texts.append(text)
        return "\n".join(texts).strip()

    def run_turn(self, user_input: str) -> Dict[str, Any]:
        self.history.append(
            self._types.UserContent(parts=[self._types.Part.from_text(text=user_input)])
        )

        response = self._create_response()
        used_tools = False
        tool_rounds = 0

        while True:
            function_calls = getattr(response, "function_calls", None) or []
            candidate_content = self._first_candidate_content(response)
            if candidate_content is not None:
                self.history.append(candidate_content)

            if not function_calls:
                return {
                    "response_id": None,
                    "text": self._safe_output_text(response),
                    "used_tools": used_tools,
                }

            tool_rounds += 1
            used_tools = True
            if tool_rounds > self.max_tool_rounds:
                return {
                    "response_id": None,
                    "text": "Agent đã chạm giới hạn số vòng gọi tool. Hãy thử yêu cầu ngắn gọn hơn.",
                    "used_tools": True,
                }

            for function_call in function_calls:
                tool_name = getattr(function_call, "name", "")
                tool_args = getattr(function_call, "args", None) or {}

                if not isinstance(tool_args, dict):
                    result = {"error": f"Tool arguments không hợp lệ: {tool_args}"}
                else:
                    tool = TOOL_REGISTRY.get(tool_name)
                    if tool is None:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    else:
                        try:
                            result = tool(**tool_args)
                        except Exception as exc:  # pragma: no cover
                            result = {"error": str(exc)}

                self.history.append(
                    self._types.Content(
                        role="tool",
                        parts=[
                            self._types.Part.from_function_response(
                                name=tool_name,
                                response=result,
                            )
                        ],
                    )
                )

            response = self._create_response()

    def reset(self) -> None:
        self.history.clear()


class EmailDraftAgent:
    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tool_rounds: int = 5,
    ) -> None:
        provider_name = _get_provider_name(provider)
        backend_cls = OpenAIEmailBackend if provider_name == "openai" else GeminiEmailBackend
        self.backend = backend_cls(model=model, max_tool_rounds=max_tool_rounds)
        self.provider = self.backend.provider_name
        self.model = self.backend.model

    def run_turn(self, user_input: str) -> Dict[str, Any]:
        return self.backend.run_turn(user_input)

    def reset(self) -> None:
        self.backend.reset()
