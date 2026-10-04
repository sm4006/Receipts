"""Local Ollama claim extraction with strict deterministic validation."""

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import Claim

DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
MODEL_ENVIRONMENT_VARIABLE = "RECEIPTS_OLLAMA_MODEL"


class AIExtractionError(RuntimeError):
    """The local model returned output that could not be safely accepted."""


class LocalAIUnavailableError(AIExtractionError):
    """The configured local Ollama service or model could not be reached."""


class _RetryableAIResponseError(AIExtractionError):
    """The model response was not parseable and may be retried once."""


@dataclass(frozen=True)
class ExtractionConfig:
    model: str
    endpoint: str = DEFAULT_OLLAMA_ENDPOINT

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise AIExtractionError("Ollama endpoint must use the local HTTP service.")

    @classmethod
    def from_environment(cls, model: Optional[str] = None, endpoint: Optional[str] = None) -> "ExtractionConfig":
        selected_model = model or os.environ.get(MODEL_ENVIRONMENT_VARIABLE, DEFAULT_OLLAMA_MODEL)
        return cls(selected_model, endpoint or DEFAULT_OLLAMA_ENDPOINT)


def extraction_prompt(documentation: str, strict_json: bool = False) -> str:
    strictness = "Return JSON only. Do not include markdown fences or commentary." if strict_json else "Return JSON only."
    return f"""Extract factual claims from the documentation below.
Extract factual claims only. Quote the exact source text.
Do not verify claims, assign verdicts, or invent evidence.
Return exactly this JSON structure: {{"claims": [{{"quote": "...", "subject": "...", "attribute": "...", "value": ..., "unit": "..."}}]}}.
Every claim object must contain exactly these five keys: quote, subject, attribute, value, unit.
Do not add keys such as verdict, evidence, confidence, or explanation.
Use null for unit when the claim has no unit.
Use the metric name stated in the source as the attribute name (for example,
precision stays precision and recall stays recall).
Do not replace an attribute with a synonym or a generic name such as value,
duration, or measurement. Use a canonical evidence name such as dataset_rows
or training_time only when that exact name is explicitly present in the
supplied documentation; otherwise preserve the source wording and do not
invent a semantic mapping.
{strictness}

DOCUMENTATION:
{documentation}"""


def _safe_json_value(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(text):
            if character not in "[{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
                return value
            except json.JSONDecodeError:
                continue
    raise _RetryableAIResponseError("AI extraction returned invalid JSON.")


def _validate_payload(payload: Any, documentation: str, source_file: Optional[str]) -> List[Claim]:
    if not isinstance(payload, dict) or set(payload) != {"claims"} or not isinstance(payload["claims"], list):
        raise AIExtractionError("AI extraction returned an invalid claims structure.")

    claims: List[Claim] = []
    required = {"quote", "subject", "attribute", "value", "unit"}
    for index, item in enumerate(payload["claims"]):
        if not isinstance(item, dict) or set(item) != required:
            raise AIExtractionError(f"AI claim {index} is missing required fields or contains unsupported fields.")
        if not all(isinstance(item[field], str) and item[field].strip() for field in ("quote", "subject", "attribute")):
            raise AIExtractionError(f"AI claim {index} has invalid text fields.")
        if item["unit"] is not None and not isinstance(item["unit"], str):
            raise AIExtractionError(f"AI claim {index} has an invalid unit.")
        if not isinstance(item["value"], (str, int, float, bool)) and item["value"] is not None:
            raise AIExtractionError(f"AI claim {index} is unsupported by the deterministic verifier.")
        if item["quote"] not in documentation:
            raise AIExtractionError(f"AI claim {index} contains a fabricated quote.")
        claims.append(
            Claim(
                quote=item["quote"],
                subject=item["subject"],
                attribute=item["attribute"],
                value=item["value"],
                unit=item["unit"],
                source_file=source_file,
            )
        )
    return claims


def extract_claims(
    documentation: str,
    source_file: Optional[str] = None,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    opener: Callable[..., Any] = urlopen,
) -> List[Claim]:
    """Extract validated claims from documentation using local Ollama only."""
    config = ExtractionConfig.from_environment(model=model, endpoint=endpoint)

    def request(prompt: str) -> str:
        body = json.dumps({"model": config.model, "prompt": prompt, "stream": False}).encode("utf-8")
        request = Request(config.endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with opener(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise LocalAIUnavailableError(
                f"Local AI extraction is unavailable at {config.endpoint}: {exc}"
            ) from exc
        try:
            envelope = json.loads(response_body)
            response_text = envelope["response"]
            if not isinstance(response_text, str):
                raise TypeError("response must be a string")
            return response_text
        except (json.JSONDecodeError, KeyError, TypeError):
            raise _RetryableAIResponseError("Ollama returned an invalid response envelope.") from None

    first_response = request(extraction_prompt(documentation))
    try:
        return _validate_payload(_safe_json_value(first_response), documentation, source_file)
    except _RetryableAIResponseError:
        second_response = request(extraction_prompt(documentation, strict_json=True))
        try:
            return _validate_payload(_safe_json_value(second_response), documentation, source_file)
        except AIExtractionError as exc:
            raise AIExtractionError(f"AI extraction failed after one retry: {exc}") from exc
