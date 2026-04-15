import json
from typing import Iterator

from openai import OpenAI

from .config import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LPA_MODEL,
    MAX_TOOL_ITERATIONS,
    REQUEST_TIMEOUT_S,
)
from .tools import TOOL_SCHEMAS, dispatch_tool

SYSTEM_PROMPT = """Du bist ein hilfreicher Assistent, der Fragen zu Lipoprotein(a) (Lp(a)) beantwortet.

Du hast Zugriff auf eine kuratierte Wissensdatenbank aus Markdown-Dateien mit wissenschaftlicher Literatur zu Lp(a).
Nutze IMMER die bereitgestellten Tools, um relevante Informationen aus der Wissensdatenbank zu finden, bevor du antwortest.
Rate oder erfinde keine Fakten.

Arbeitsweise:
1. Rufe `list_files` auf, um einen Überblick über die verfügbaren Dateien zu erhalten (falls noch nicht geschehen).
2. Nutze `keyword_search`, um relevante Stellen zu finden.
3. Nutze `read_file`, um die kompletten relevanten Dateien zu lesen.
4. Beantworte die Frage des Nutzers präzise, gut strukturiert und basierend ausschließlich auf den gelesenen Dateien.
5. Zitiere am Ende deiner Antwort die verwendeten Dateien im Format:
   **Quellen:** `datei1.md`, `datei2.md`

Wenn die Wissensdatenbank keine Antwort hergibt, sage das ehrlich.
Antworte standardmäßig auf Deutsch. Wenn der Nutzer auf Englisch schreibt, antworte auf Englisch.
"""


def _client() -> OpenAI:
    return OpenAI(
        base_url=LITELLM_BASE_URL,
        api_key=LITELLM_API_KEY,
        timeout=REQUEST_TIMEOUT_S,
    )


def _preview(s: str, n: int = 400) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def run_agent(user_messages: list[dict]) -> Iterator[dict]:
    """Drive the tool-calling loop and yield events.

    Events: {"type": "tool_call", "name", "arguments"}
            {"type": "tool_result", "name", "result_preview"}
            {"type": "answer", "content"}
            {"type": "error", "message"}
    """
    client = _client()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in user_messages:
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = client.chat.completions.create(
            model=LPA_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool_call", "name": name, "arguments": args}
                try:
                    result = dispatch_tool(name, args)
                except Exception as e:  # noqa: BLE001
                    result = f"ERROR: {e}"
                result_str = (
                    result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                )
                yield {
                    "type": "tool_result",
                    "name": name,
                    "result_preview": _preview(result_str),
                }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    }
                )
            continue

        yield {"type": "answer", "content": msg.content or ""}
        return

    yield {
        "type": "answer",
        "content": "Fehler: Maximale Anzahl an Tool-Aufrufen erreicht, ohne zu einer Antwort zu kommen.",
    }
