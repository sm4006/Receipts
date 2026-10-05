"""Local Ollama claim extraction with strict deterministic validation."""

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import Claim

DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_TIMEOUT = 180
MODEL_ENVIRONMENT_VARIABLE = "RECEIPTS_OLLAMA_MODEL"
TIMEOUT_ENVIRONMENT_VARIABLE = "RECEIPTS_OLLAMA_TIMEOUT"
_GROUNDING_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "our", "the", "this", "to", "was",
    "were", "with",
}
_CONFIGURATION_PATTERNS = (
    r"\bconfigured\s+\w+\s+(?:is|was|=)\b",
    r"\b(?:model|algorithm|classifier|estimator)\s+(?:used|selected|chosen|is|was)\b",
    r"\b(?:uses|used|selected|configured|set)\s+\w+\s+(?:as|to|for)\b",
)


class AIExtractionError(RuntimeError):
    """The local model returned output that could not be safely accepted."""


class LocalAIUnavailableError(AIExtractionError):
    """The configured local Ollama service or model could not be reached."""


class _RetryableAIResponseError(AIExtractionError):
    """The model response was invalid and may be retried once."""


@dataclass(frozen=True)
class ExtractionConfig:
    model: str
    endpoint: str = DEFAULT_OLLAMA_ENDPOINT
    timeout: float = DEFAULT_OLLAMA_TIMEOUT

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise AIExtractionError("Ollama endpoint must use the local HTTP service.")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise AIExtractionError("Ollama timeout must be a positive number.")

    @classmethod
    def from_environment(
        cls,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> "ExtractionConfig":
        selected_model = model or os.environ.get(MODEL_ENVIRONMENT_VARIABLE, DEFAULT_OLLAMA_MODEL)
        selected_timeout = timeout
        if selected_timeout is None:
            configured_timeout = os.environ.get(TIMEOUT_ENVIRONMENT_VARIABLE)
            if configured_timeout is None:
                selected_timeout = DEFAULT_OLLAMA_TIMEOUT
            else:
                try:
                    selected_timeout = float(configured_timeout)
                except ValueError as exc:
                    raise AIExtractionError("Ollama timeout must be a positive number.") from exc
        return cls(selected_model, endpoint or DEFAULT_OLLAMA_ENDPOINT, selected_timeout)


def extraction_prompt(documentation: str, strict_json: bool = False) -> str:
    strictness = "Return JSON only. Do not include markdown fences or commentary." if strict_json else "Return JSON only."
    return f"""Extract factual claims from the documentation below.
Extract only concrete factual statements that are candidates for deterministic
evidence verification. A claim must state a measurable value or an explicitly
configured project fact that could appear in a CSV, JSON, or notebook evidence
entry.
Ignore project descriptions, marketing prose, feature headings, technology
name lists, generic qualitative statements, recommendations, explanatory prose
without a measurable or configured fact, and standalone labels or bullets
without a verifiable value. Do not extract headings such as "DNA Encoding
Visualization" or technology names such as HTML5, CSS3, JavaScript, or GitHub
Pages merely because they appear in the documentation.
Quote the exact source text.
Do not verify claims, assign verdicts, or invent evidence.
Return exactly this JSON structure: {{"claims": [{{"quote": "...", "subject": "...", "attribute": "...", "value": ..., "unit": "..."}}]}}.
Every claim object must contain exactly these five keys: quote, subject, attribute, value, unit.
Do not add keys such as verdict, evidence, confidence, or explanation.
Use null for unit when the claim has no unit.
Keep claims such as accuracy = 91.8%, precision = 0.80, recall = 0.80,
epochs = 50, dataset_rows = 10000, training_time = 42 seconds, or an explicitly
stated model_name such as RandomForest when they are present in the source.
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


def _grounding_tokens(text: str) -> List[str]:
    tokens = re.findall(r"\d[\d,]*(?:\.\d+)?|[a-z]+(?:[._-][a-z0-9]+)*", text.casefold())
    tokens = [token.replace(",", "") if token[0].isdigit() else token for token in tokens]
    return [token for token in tokens if token not in _GROUNDING_STOP_WORDS]


def _source_passages(documentation: str) -> List[str]:
    return [
        passage.strip()
        for passage in re.split(r"(?<=[.!?])\s+|\r?\n+", documentation)
        if passage.strip()
    ]


def _ground_quote(quote: str, value: Any, documentation: str) -> str:
    if quote in documentation:
        return quote

    quote_tokens = set(_grounding_tokens(quote))
    if not quote_tokens:
        raise _RetryableAIResponseError("AI claim contains a fabricated quote.")
    value_tokens = set(_grounding_tokens(str(value))) if value is not None else set()
    numeric_tokens = {token for token in quote_tokens if any(character.isdigit() for character in token)}
    candidates = []
    for passage in _source_passages(documentation):
        passage_tokens = set(_grounding_tokens(passage))
        overlap = quote_tokens & passage_tokens
        if numeric_tokens and not numeric_tokens <= passage_tokens:
            continue
        if value_tokens and not value_tokens <= passage_tokens:
            continue
        if len(overlap) < 2 or len(overlap) / len(quote_tokens) < 0.5:
            continue
        candidates.append((len(overlap) / len(quote_tokens), passage))

    if not candidates:
        raise _RetryableAIResponseError("AI claim contains a fabricated quote.")
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise _RetryableAIResponseError("AI claim quote matches multiple source passages.")
    return candidates[0][1]


def _is_quality_claim(quote: str, value: Any) -> bool:
    """Accept measurable facts and explicit configuration statements only."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    if len(_grounding_tokens(quote)) < 2:
        return False
    return any(re.search(pattern, quote, re.IGNORECASE) for pattern in _CONFIGURATION_PATTERNS)


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
        grounded_quote = _ground_quote(item["quote"], item["value"], documentation)
        if not _is_quality_claim(grounded_quote, item["value"]):
            continue
        claims.append(
            Claim(
                quote=grounded_quote,
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
    timeout: Optional[float] = None,
    opener: Callable[..., Any] = urlopen,
) -> List[Claim]:
    """Extract validated claims from documentation using local Ollama only."""
    config = ExtractionConfig.from_environment(model=model, endpoint=endpoint, timeout=timeout)

    def request(prompt: str) -> str:
        body = json.dumps({"model": config.model, "prompt": prompt, "stream": False}).encode("utf-8")
        request = Request(config.endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with opener(request, timeout=config.timeout) as response:
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
