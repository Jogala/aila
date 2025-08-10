"""
Legal Document Change Analyzer - Core Analysis Engine

This module provides AI-powered analysis of legal document changes using modern LLMs.
It uses a pure functional approach with provider configuration for clean separation of concerns.
"""

import json
import logging
import os
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Optional, TypedDict, Union

from pydantic import BaseModel, Field

import aila.llm_interface as llm_interface
from aila.config import get_config
from aila.load_document import load_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChangeType(StrEnum):
    """Types of changes that can be detected in legal documents."""

    CRITICAL = "Critical"  # High legal/financial impact
    MINOR = "Minor"  # Medium impact, clarifications
    FORMATTING = "Formatting"  # Low impact, cosmetic changes


class DocumentChange(BaseModel):
    """Represents a single change between document versions."""

    change_id: str = Field(..., description="Unique identifier for the change")
    change_type: ChangeType = Field(..., description="Type of change (Critical, Minor, Formatting)")
    old_text: str = Field(..., description="Original text")
    new_text: str = Field(..., description="Updated text")
    section: str = Field(..., description="Document section where change occurred")
    description: str = Field(..., description="Description of the change")
    legal_implications: str = Field(..., description="Legal implications of the change")
    affected_parties: list[str] = Field(default_factory=list, description="Parties affected by the change")


class Summary(BaseModel):
    """Summary of the analysis results."""

    critical_changes: int = Field(..., ge=0, description="Number of critical changes")
    minor_changes: int = Field(..., ge=0, description="Number of minor changes")
    formatting_changes: int = Field(..., ge=0, description="Number of formatting changes")
    most_affected_party: str
    overall_assessment: str

    @property
    def total_changes(self) -> int:
        return self.critical_changes + self.minor_changes + self.formatting_changes


class AnalysisResult(BaseModel):
    """Complete analysis result for a document comparison."""

    document1_name: str
    document2_name: str
    analysis_timestamp: str
    llm_config: llm_interface.LlmConfig
    changes: list[DocumentChange]
    summary: Summary


def analyze_documents_on_disk(
    llm_interface: llm_interface.LlmInterface, doc1_path: Path, doc2_path: Path, prompt_template: str
) -> AnalysisResult:
    logger.info(f"Starting analysis: {doc1_path} vs {doc2_path}")

    doc1_text = load_document(doc1_path)
    doc2_text = load_document(doc2_path)

    result = analyze_documents(
        llm_interface=llm_interface,
        doc1_text=doc1_text,
        doc2_text=doc2_text,
        name_doc1=doc1_path.name,
        name_doc2=doc2_path.name,
        prompt_template=prompt_template,
    )
    logger.info("Analysis completed successfully")
    return result


def analyze_documents(
    llm_interface: llm_interface.LlmInterface,
    doc1_text: str,
    doc2_text: str,
    name_doc1: str,
    name_doc2: str,
    prompt_template: str,
) -> AnalysisResult:
    prompt = create_analysis_prompt(doc1_text, doc2_text, prompt_template)
    # call LLM
    response = llm_interface.analyze_fn(prompt)

    if get_config().log_llm_responses:
        path_logging = get_config().path_logging_llm_responses
        path_logging.parent.mkdir(parents=True, exist_ok=True)
        with open(path_logging, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now().isoformat()} - {name_doc1} vs {name_doc2}, {prompt_template}, {llm_interface.llm_config.model_dump()}:\n{response}\n\n"
            )

    summary, changes = parse_llm_response(response)

    result = AnalysisResult(
        llm_config=llm_interface.llm_config,
        document1_name=name_doc1,
        document2_name=name_doc2,
        changes=changes,
        summary=summary,
        analysis_timestamp=datetime.now().isoformat(),
    )

    logger.info("Analysis completed successfully")
    return result


def create_analysis_prompt(doc1: str, doc2: str, prompt_template: str) -> str:
    template_content = load_document(get_config().prompt_templates_dir / prompt_template)

    prompt_json = """{{
    "document_comparison": {{
        "document1": "<name of document 1>",
        "document2": "<name of document 2>", 
        "analysis_date": "<current date>",
        "total_changes": <number of changes found>
    }},
    "parties_identified": [
        "<party 1>",
        "<party 2>",
        "<party 3>",
        "..."
    ],
    "changes": [
        {{
        "change_id": <sequential number>,
        "location": "<where in document - section number, heading, or description>",
        "change_type": "<Critical | Minor | Formatting>",
        "old_text": "<exact text from document 1>",
        "new_text": "<exact text from document 2>",
        "description": "<brief description of what changed>",
        "legal_significance": "<detailed explanation of legal impact and implications>",
        "affected_parties": ["<which of the identified parties is affected>"]
        }}
    ],
    "summary": {{
        "critical_changes": <count>,
        "minor_changes": <count>,
        "formatting_changes": <count>,
        "most_affected_party": "<use parties identified above>",
        "overall_assessment": "<comprehensive summary of changes and their implications>"
    }}
    }}"""

    prompt = template_content.replace(r"{doc1}", doc1)
    prompt = prompt.replace(r"{doc2}", doc2)
    prompt = prompt.replace(r"{json}", prompt_json)

    return prompt


def parse_llm_response(response: str) -> tuple[Summary, list[DocumentChange]]:
    """Parse LLM response into DocumentChange objects."""
    try:
        logger.info(f"Raw LLM response: {response}...")  # Log first 500 chars for debugging

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in LLM response")

        json_str = json_match.group()
        logger.info(f"Extracted JSON: {json_str}...")  # Log extracted JSON
        data = json.loads(json_str)

        changes: list[DocumentChange] = []
        list_changes_json = data.get("changes", [])
        for change_data in list_changes_json:
            affected_party = change_data.get("affected_party", "")
            affected_parties = [affected_party] if affected_party else []

            change = DocumentChange(
                change_id=str(change_data.get("change_id", "")),
                change_type=ChangeType(change_data.get("change_type", "Minor")),
                old_text=change_data.get("old_text", ""),
                new_text=change_data.get("new_text", ""),
                section=change_data.get("location", "Unknown"),
                description=change_data.get("description", ""),
                legal_implications=change_data.get("legal_significance", ""),
                affected_parties=affected_parties,
            )
            changes.append(change)

        summary_json = data.get("summary", {})
        summary = Summary(
            critical_changes=summary_json.get("critical_changes", 0),
            minor_changes=summary_json.get("minor_changes", 0),
            formatting_changes=summary_json.get("formatting_changes", 0),
            most_affected_party=summary_json.get("most_affected_party", ""),
            overall_assessment=summary_json.get("overall_assessment", ""),
        )

        return summary, changes

    except Exception as e:
        logger.error(f"Error parsing LLM response: {e}")
        raise ValueError(f"Failed to parse LLM response: {e}")


def save_results_to_json(result: AnalysisResult, output_path: Path) -> None:
    results_json = result.model_dump(mode="json", exclude_none=True, by_alias=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)
