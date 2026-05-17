from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_CATALOG_DESC_RE = re.compile(r"Catalog\s+Description:\s*(.+)", re.IGNORECASE)
_SENTENCE_BREAK_RE = re.compile(r"\.\s+[A-Z]")
_TITLE_PIPE_RE = re.compile(r"^(.+?)\s*\|\s*(.+)$")
_SIMPLE_MPN_RE = re.compile(r"^[\w+\-.]+$")
_ABB_INTERNAL_ID_RE = re.compile(r"new\.abb\.com/products/([A-Za-z0-9]+)/")

from product_retrieval.config import Settings
from product_retrieval.context_builder import build_evidence_text
from product_retrieval.models import ProductEnrichmentOutput, SearchResult

from llm.output_parser import parse_llm_json
from llm.prompts import SYSTEM_EXTRACTION_PROMPT, build_user_extraction_prompt


class ProductExtractor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm: Any | None = None
        self._prompt: Any | None = None
        self._parser: Any | None = None
        self._langfuse: Any | None = None
        if settings.langfuse_public_key:
            try:
                from langfuse import Langfuse
                self._langfuse = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_base_url,
                )
            except Exception:
                pass

    def extract(self, gtin: str, evidence_items: list[SearchResult]) -> tuple[ProductEnrichmentOutput, str]:
        llm, prompt, parser = self._components()
        evidence_text = build_evidence_text(evidence_items)
        messages = prompt.invoke(
            {
                "gtin": gtin,
                "evidence_text": evidence_text,
                "format_instructions": parser.get_format_instructions(),
            }
        )
        callbacks = self._langfuse_callbacks(gtin)
        response = llm.invoke(messages, config={"callbacks": callbacks} if callbacks else {})
        raw_output = response.content if hasattr(response, "content") else str(response)
        try:
            parsed = parser.parse(raw_output)
            candidate = parsed.model_dump(mode="json")
        except Exception:
            candidate = raw_output
        normalized = normalize_llm_payload(candidate, gtin, [item.url for item in evidence_items])
        normalized = _enrich_from_evidence(normalized, evidence_items)
        validated = parse_llm_json(normalized, ProductEnrichmentOutput)
        return validated, raw_output

    def _langfuse_callbacks(self, gtin: str) -> list:
        if self._langfuse is None:
            return []
        try:
            from langfuse.langchain import CallbackHandler
            return [CallbackHandler(public_key=self.settings.langfuse_public_key)]
        except Exception as exc:
            logger.warning("Langfuse callback unavailable: %s", exc)
            return []

    def _components(self) -> tuple[Any, Any, Any]:
        if self._llm is None:
            from langchain_core.output_parsers import PydanticOutputParser
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI

            self._parser = PydanticOutputParser(pydantic_object=ProductEnrichmentOutput)
            self._prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_EXTRACTION_PROMPT),
                    ("user", build_user_extraction_prompt(
                        gtin="{gtin}",
                        evidence_text="{evidence_text}",
                        format_instructions="{format_instructions}",
                    )),
                ]
            )
            self._llm = ChatOpenAI(
                base_url=self.settings.llama_cpp_base_url,
                api_key=self.settings.llama_cpp_api_key,
                model=self.settings.llama_cpp_model,
                temperature=0,
                max_tokens=self.settings.llm_max_tokens,
            )
        return self._llm, self._prompt, self._parser


class MockProductExtractor:
    def extract(self, gtin: str, evidence_items: list[SearchResult]) -> tuple[ProductEnrichmentOutput, str]:
        source_urls = [item.url for item in evidence_items]
        output = ProductEnrichmentOutput(
            original_reference=gtin,
            product_name=None,
            manufacturer=None,
            manufacturer_product_id=None,
            serial_number=None,
            item_class=None,
            category=None,
            description=None,
            technical_specs={},
            source_urls=source_urls,
            confidence_score=0,
            missing_fields=[
                "product_name",
                "manufacturer",
                "manufacturer_product_id",
                "serial_number",
                "item_class",
                "category",
                "description",
            ],
        )
        return output, json.dumps(output.model_dump(mode="json"), ensure_ascii=False)


def normalize_llm_payload(raw_output: str | dict, gtin: str, allowed_urls: list[str] | None = None) -> dict:
    payload = raw_output if isinstance(raw_output, dict) else _extract_json_payload(raw_output)
    source_urls = payload.get("source_urls")
    if not isinstance(source_urls, list):
        source_urls = []
    if allowed_urls is not None:
        allowed_url_set = set(allowed_urls)
        source_urls = [url for url in source_urls if url in allowed_url_set]
    technical_specs = payload.get("technical_specs")
    if not isinstance(technical_specs, dict):
        technical_specs = {}
    technical_specs = {k: str(v) for k, v in technical_specs.items() if v is not None}
    confidence_score = payload.get("confidence_score")
    if not isinstance(confidence_score, (int, float)):
        confidence_score = 0.0
    manufacturer = payload.get("manufacturer") or payload.get("brand")
    manufacturer_product_id = (
        payload.get("manufacturer_product_id")
        or payload.get("product_id")
        or payload.get("model")
    )
    # If neither of the two most critical fields could be extracted, the score is meaningless.
    if not manufacturer and not manufacturer_product_id:
        confidence_score = 0.0
    normalized = {
        "original_reference": gtin,
        "product_name": payload.get("product_name"),
        "manufacturer": manufacturer,
        "manufacturer_product_id": manufacturer_product_id,
        "serial_number": payload.get("serial_number"),
        "item_class": payload.get("item_class"),
        "category": payload.get("category"),
        "description": payload.get("description"),
        "technical_specs": technical_specs,
        "source_urls": source_urls,
        "confidence_score": float(confidence_score),
        "missing_fields": payload.get("missing_fields") if isinstance(payload.get("missing_fields"), list) else [],
        "is_electrical_or_industrial_product": bool(payload.get("is_electrical_or_industrial_product", True)),
    }
    return normalized


def _catalog_desc_from_snippet(snippet: str) -> str | None:
    m = _CATALOG_DESC_RE.search(snippet)
    if not m:
        return None
    raw = m.group(1)
    stop = _SENTENCE_BREAK_RE.search(raw)
    if stop:
        raw = raw[: stop.start()]
    raw = re.sub(r"\s*\.\.\.\s*$", "", raw).strip("., ")
    return raw or None


def _looks_like_internal_id(value: str) -> bool:
    # all-alphanumeric IDs (no hyphens/plus) are typically internal DB keys, not human-facing MPNs
    return bool(re.fullmatch(r"[A-Za-z0-9]{8,}", value))


def _enrich_from_evidence(payload: dict, evidence_items: list[SearchResult]) -> dict:
    payload = dict(payload)

    title_mpns: list[str] = []
    title_manufacturers: list[str] = []
    catalog_descs: list[str] = []
    abb_internal_ids: list[str] = []

    for item in evidence_items:
        m = _TITLE_PIPE_RE.match(item.title.strip())
        if m:
            mpn_candidate = m.group(1).strip()
            mfr_candidate = m.group(2).strip()
            if _SIMPLE_MPN_RE.match(mpn_candidate):
                title_mpns.append(mpn_candidate)
                if mfr_candidate:
                    title_manufacturers.append(mfr_candidate)

        desc = _catalog_desc_from_snippet(item.snippet)
        if desc:
            catalog_descs.append(desc)

        m2 = _ABB_INTERNAL_ID_RE.search(item.url)
        if m2:
            abb_internal_ids.append(m2.group(1))

    # product_name: catalog description always wins (authoritative); fall back to title MPN
    if catalog_descs:
        payload["product_name"] = catalog_descs[0]
    elif not payload.get("product_name") and title_mpns:
        payload["product_name"] = title_mpns[0]

    # manufacturer_product_id: prefer title MPN over internal-looking IDs from LLM
    current_mpn = payload.get("manufacturer_product_id")
    if title_mpns and (not current_mpn or _looks_like_internal_id(str(current_mpn))):
        payload["manufacturer_product_id"] = title_mpns[0]

    # manufacturer: fill from title if missing
    if not payload.get("manufacturer") and title_manufacturers:
        payload["manufacturer"] = title_manufacturers[0]

    # store ABB internal product ID in technical_specs so it is not lost
    if abb_internal_ids:
        specs = dict(payload.get("technical_specs") or {})
        specs.setdefault("abb_product_id", abb_internal_ids[0])
        payload["technical_specs"] = specs

    # remove from missing_fields any field we just populated
    newly_filled = {k for k in ("product_name", "manufacturer", "manufacturer_product_id") if payload.get(k)}
    if newly_filled:
        payload["missing_fields"] = [f for f in (payload.get("missing_fields") or []) if f not in newly_filled]

    return payload


def _extract_json_payload(raw_output: str) -> dict:
    match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
