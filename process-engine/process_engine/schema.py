"""Process definition schema (Pydantic) for Office IDE Phase 4.

Steps are ordered and typed: rag_query | plugin_call | llm_transform.
Email-draft outputs always carry never_send=True in v1 (TASKS #14).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StepType(str, Enum):
    RAG_QUERY = "rag_query"
    PLUGIN_CALL = "plugin_call"
    LLM_TRANSFORM = "llm_transform"


class ArtifactType(str, Enum):
    EMAIL_DRAFT = "email_draft"
    TEXT = "text"


class ProcessInput(BaseModel):
    """Declared input parameter collected conversationally or via MCP args."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    type: Literal["string", "text", "email"] = "string"
    description: str = ""
    required: bool = True
    default: Optional[str] = None


class RagQueryStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    type: Literal["rag_query"] = "rag_query"
    query_template: str = Field(
        ...,
        min_length=1,
        description="Jinja-like placeholders {{input_name}} resolved from inputs + prior step outputs.",
    )
    top_k: int = Field(default=5, ge=1, le=20)
    namespace_hint: Optional[str] = None


class PluginCallStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    type: Literal["plugin_call"] = "plugin_call"
    plugin: str = Field(..., min_length=1, description="MCP plugin id, e.g. sharepoint")
    tool: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    # v1: only read/search/draft scopes; send is rejected by policy elsewhere.
    scope: Literal["read", "search", "draft"] = "read"


class LlmTransformStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    type: Literal["llm_transform"] = "llm_transform"
    prompt_template: str = Field(..., min_length=1)
    input_refs: List[str] = Field(
        default_factory=list,
        description="Prior step ids whose outputs are injected into the prompt context.",
    )


ProcessStep = Union[RagQueryStep, PluginCallStep, LlmTransformStep]


class OutputTemplate(BaseModel):
    """Artifact produced by the process. Email drafts never auto-send in v1."""

    model_config = ConfigDict(extra="forbid")

    artifact_type: ArtifactType = ArtifactType.EMAIL_DRAFT
    subject_template: str = ""
    body_template: str = Field(..., min_length=1)
    never_send: bool = Field(
        default=True,
        description="Hard policy: email_draft artifacts must never be delivered by the runner.",
    )

    @model_validator(mode="after")
    def _enforce_never_send_for_email(self) -> OutputTemplate:
        if self.artifact_type is ArtifactType.EMAIL_DRAFT and not self.never_send:
            raise ValueError(
                "email_draft output_template.never_send must be true (never-send policy v1)"
            )
        return self


class ProcessDefinition(BaseModel):
    """Versioned, parameterized process definition."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    version: str = Field(..., min_length=1, description="Semver or integer string, e.g. '1' or '1.0.0'")
    tenant_id: Optional[str] = Field(
        default=None,
        description="Owning tenant; null means shared/catalog template.",
    )
    title: str = Field(..., min_length=1)
    description: str = ""
    inputs: List[ProcessInput] = Field(default_factory=list)
    steps: List[ProcessStep] = Field(..., min_length=1)
    output_template: OutputTemplate

    @field_validator("steps")
    @classmethod
    def _unique_step_ids(cls, steps: List[ProcessStep]) -> List[ProcessStep]:
        seen: set[str] = set()
        for step in steps:
            if step.id in seen:
                raise ValueError(f"duplicate step id: {step.id!r}")
            seen.add(step.id)
        return steps

    @model_validator(mode="after")
    def _input_refs_resolve(self) -> ProcessDefinition:
        step_ids = {s.id for s in self.steps}
        for step in self.steps:
            if isinstance(step, LlmTransformStep):
                missing = [r for r in step.input_refs if r not in step_ids]
                if missing:
                    raise ValueError(
                        f"step {step.id!r} input_refs unknown: {missing}"
                    )
        return self

    def catalog_key(self) -> str:
        return f"{self.id}@{self.version}"


def validate_process_dict(data: Dict[str, Any]) -> ProcessDefinition:
    """Validate a raw dict (e.g. loaded JSON) into a ProcessDefinition."""
    return ProcessDefinition.model_validate(data)


def process_json_schema() -> Dict[str, Any]:
    """Export JSON Schema for ProcessDefinition (docs / external validators)."""
    return ProcessDefinition.model_json_schema()
