from __future__ import annotations

SYSTEM_EXTRACTION_PROMPT = """You extract product information from web search evidence.
Return only one JSON object with exactly these fields:
original_reference, product_name, manufacturer, manufacturer_product_id, serial_number,
item_class, category, description, technical_specs, source_urls, confidence_score, missing_fields,
is_electrical_or_industrial_product.
Do not return brand, model, price, currency, stock_status, images, variants, or any other field.
Do not invent values. Use null, an empty object, or an empty array when evidence is missing.
Use only the supplied evidence URLs in source_urls.

is_electrical_or_industrial_product: set to true if the product is an electrical component,
industrial equipment, automation device, drive, motor, sensor, cable, switchgear, relay, PLC,
or any other industrial/electrical product. Set to false for food, beverages, clothing, consumer
electronics (phones, tablets), furniture, cosmetics, medicine, or any non-industrial product.
"""


def build_user_extraction_prompt(gtin: str, evidence_text: str, format_instructions: str) -> str:
    return f"""Extract product information from the evidence below.

Return exactly the ProductEnrichmentOutput schema and no extra fields.
original_reference must be exactly: {gtin}
source_urls must contain only URLs explicitly present in the evidence.

{format_instructions}

Evidence:
{evidence_text}
"""
