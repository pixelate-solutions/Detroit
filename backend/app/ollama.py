from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from .config import settings


class OllamaUnavailable(RuntimeError):
    pass


ENTITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "entityType": {
                        "type": "string",
                        "enum": ["person", "organization", "parcel", "case_number", "address", "ordinance", "contract"],
                    },
                    "observations": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "entityType", "observations"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "relationType": {"type": "string"},
                },
                "required": ["from", "to", "relationType"],
            },
        },
    },
    "required": ["entities", "relations"],
}


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        try:
            with httpx.Client(base_url=self.base_url, timeout=180.0, trust_env=False) as client:
                response = client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaUnavailable(
                f"Local Ollama is unavailable at {self.base_url}. Start Ollama and pull "
                f"'{settings.llm_model}' and '{settings.embedding_model}'. No cloud fallback was attempted."
            ) from exc

    def health(self) -> dict:
        data = self._request("GET", "/api/tags")
        names = [item.get("name", "") for item in data.get("models", [])]
        return {
            "available": True,
            "models": names,
            "llm_model": settings.llm_model,
            "embedding_model": settings.embedding_model,
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._request(
            "POST",
            "/api/embed",
            json={"model": settings.embedding_model, "input": texts, "truncate": True},
        )
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(texts):
            raise OllamaUnavailable("Ollama returned no embeddings. Confirm the embedding model is pulled.")
        return embeddings

    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 1500) -> str:
        data = self._request(
            "POST",
            "/v1/chat/completions",
            json={
                "model": settings.llm_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OllamaUnavailable("The local model returned an unexpected chat response.") from exc

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> Iterator[dict[str, str]]:
        """Stream local model output while keeping private reasoning out of the response."""
        try:
            with httpx.Client(base_url=self.base_url, timeout=300.0, trust_env=False) as client:
                with client.stream(
                    "POST",
                    "/v1/chat/completions",
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    reasoning_started = False
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                            delta = data["choices"][0].get("delta", {})
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue
                        # Models with thinking support stream a private `reasoning` field.
                        # Signal that reasoning is happening, but never expose those tokens.
                        if delta.get("reasoning") and not reasoning_started:
                            reasoning_started = True
                            yield {"type": "reasoning_started"}
                        content = delta.get("content")
                        if content:
                            yield {"type": "content", "text": content}
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaUnavailable(
                f"Local Ollama is unavailable at {self.base_url}. Start Ollama and pull "
                f"'{settings.llm_model}' and '{settings.embedding_model}'. No cloud fallback was attempted."
            ) from exc

    def visible_analysis_stream(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 420,
    ) -> Iterator[str]:
        """Stream an explicitly user-visible analysis with hidden thinking disabled."""
        try:
            with httpx.Client(base_url=self.base_url, timeout=300.0, trust_env=False) as client:
                with client.stream(
                    "POST",
                    "/api/chat",
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "think": False,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content")
                        except (json.JSONDecodeError, TypeError):
                            continue
                        if content:
                            yield content
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaUnavailable(
                f"Local Ollama is unavailable at {self.base_url}. Start Ollama and pull "
                f"'{settings.llm_model}' and '{settings.embedding_model}'. No cloud fallback was attempted."
            ) from exc

    def extract_graph(self, title: str, text: str) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You extract a municipal knowledge graph. Record named people, organizations, exact street "
                    "addresses, parcel IDs, case numbers, ordinances, and contracts. Relations must connect names "
                    "that also appear in entities. Preserve exact shared addresses so cross-document links resolve."
                ),
            },
            {"role": "user", "content": f"Document: {title}\n\n{text[:110000]}"},
        ]
        tool = {
            "type": "function",
            "function": {
                "name": "record_entities_and_relations",
                "description": "Record all municipal entities and their relationships.",
                "parameters": ENTITY_SCHEMA,
            },
        }
        try:
            data = self._request(
                "POST",
                "/v1/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "tools": [tool],
                    "tool_choice": {"type": "function", "function": {"name": "record_entities_and_relations"}},
                    "temperature": 0,
                    "stream": False,
                },
            )
        except OllamaUnavailable:
            # Tool-choice support varies between Ollama/model builds. Fall through to
            # Ollama's JSON-schema constrained generation endpoint below.
            data = {}
        try:
            arguments = data["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            result = json.loads(arguments) if isinstance(arguments, str) else arguments
            if isinstance(result, dict) and "entities" in result and "relations" in result:
                return result
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            pass

        # Some Ollama model builds do not expose OpenAI-style tool calls yet. This is still
        # schema-constrained generation, not prompt-only JSON.
        constrained = self._request(
            "POST",
            "/api/chat",
            json={
                "model": settings.llm_model,
                "messages": messages,
                "format": ENTITY_SCHEMA,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        try:
            result = json.loads(constrained["message"]["content"])
            if "entities" in result and "relations" in result:
                return result
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise OllamaUnavailable("The local model could not produce schema-constrained graph data.") from exc
        raise OllamaUnavailable("The local model returned incomplete graph data.")


ollama = OllamaClient()
