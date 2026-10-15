"""Sequential process runner with mocked RAG / plugin / LLM callouts.

v1 produces artifacts only — never sends email or posts live.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Optional, Protocol

from process_engine.schema import (
    ArtifactType,
    LlmTransformStep,
    PluginCallStep,
    ProcessDefinition,
    ProcessInput,
    RagQueryStep,
)


_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class RagClient(Protocol):
    def query(self, text: str, *, top_k: int = 5, namespace_hint: Optional[str] = None) -> Dict[str, Any]:
        ...


class PluginClient(Protocol):
    def call(
        self,
        plugin: str,
        tool: str,
        arguments: Mapping[str, Any],
        *,
        scope: str,
    ) -> Dict[str, Any]:
        ...


class LlmClient(Protocol):
    def transform(self, prompt: str, *, context: Mapping[str, Any]) -> str:
        ...


class MockRagClient:
    def query(self, text: str, *, top_k: int = 5, namespace_hint: Optional[str] = None) -> Dict[str, Any]:
        return {
            "stub": True,
            "query": text,
            "top_k": top_k,
            "namespace_hint": namespace_hint,
            "hits": [
                {
                    "rank": 1,
                    "excerpt": f"[mock RAG] Relevant policy snippet for: {text[:120]}",
                    "source": "mock://handbook/policy.md",
                }
            ],
        }


class MockPluginClient:
    def call(
        self,
        plugin: str,
        tool: str,
        arguments: Mapping[str, Any],
        *,
        scope: str,
    ) -> Dict[str, Any]:
        if scope == "send":
            raise PermissionError("never_send_v1: plugin send scope blocked in process runner")
        return {
            "stub": True,
            "plugin": plugin,
            "tool": tool,
            "scope": scope,
            "arguments": dict(arguments),
            "result": f"[mock {plugin}.{tool}] ok",
        }


class MockLlmClient:
    def transform(self, prompt: str, *, context: Mapping[str, Any]) -> str:
        # Deterministic stub: echo prompt head + note context keys.
        keys = ", ".join(sorted(context.keys())) or "(none)"
        return f"[mock LLM]\n{prompt.strip()}\n\n-- context keys: {keys}"


@dataclass
class StepTrace:
    step_id: str
    step_type: str
    output: Any


@dataclass
class ProcessRunResult:
    process_id: str
    version: str
    ok: bool
    artifact: Dict[str, Any]
    steps: list[StepTrace] = field(default_factory=list)
    error: Optional[str] = None


def render_template(template: str, values: Mapping[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"unresolved placeholder {{{{{key}}}}}")
        return str(values[key])

    return _PLACEHOLDER.sub(repl, template)


def _collect_inputs(
    definition: ProcessDefinition,
    provided: Mapping[str, Any],
) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for spec in definition.inputs:
        if spec.name in provided and provided[spec.name] is not None:
            values[spec.name] = provided[spec.name]
        elif spec.default is not None:
            values[spec.name] = spec.default
        elif spec.required:
            raise ValueError(f"missing required input: {spec.name}")
    # Allow extra keys for step output binding later; do not copy unknown inputs blindly.
    return values


class ProcessRunner:
    """Execute process steps sequentially using injectable clients (mocks by default)."""

    def __init__(
        self,
        *,
        rag: Optional[RagClient] = None,
        plugins: Optional[PluginClient] = None,
        llm: Optional[LlmClient] = None,
    ) -> None:
        self.rag = rag or MockRagClient()
        self.plugins = plugins or MockPluginClient()
        self.llm = llm or MockLlmClient()

    def run(
        self,
        definition: ProcessDefinition,
        inputs: Mapping[str, Any] | None = None,
    ) -> ProcessRunResult:
        inputs = inputs or {}
        try:
            bindings: MutableMapping[str, Any] = dict(_collect_inputs(definition, inputs))
            traces: list[StepTrace] = []

            for step in definition.steps:
                if isinstance(step, RagQueryStep):
                    query = render_template(step.query_template, bindings)
                    out = self.rag.query(
                        query,
                        top_k=step.top_k,
                        namespace_hint=step.namespace_hint,
                    )
                elif isinstance(step, PluginCallStep):
                    args = {
                        k: (render_template(v, bindings) if isinstance(v, str) else v)
                        for k, v in step.arguments.items()
                    }
                    out = self.plugins.call(
                        step.plugin,
                        step.tool,
                        args,
                        scope=step.scope,
                    )
                elif isinstance(step, LlmTransformStep):
                    ctx = {ref: bindings[ref] for ref in step.input_refs if ref in bindings}
                    prompt = render_template(step.prompt_template, bindings)
                    text = self.llm.transform(prompt, context=ctx)
                    out = {"text": text}
                else:
                    raise TypeError(f"unsupported step type: {type(step)}")

                bindings[step.id] = out
                # Convenience: first RAG hit excerpt / LLM text as flat string for templates.
                if isinstance(step, RagQueryStep) and isinstance(out, dict):
                    hits = out.get("hits") or []
                    if hits:
                        bindings[f"{step.id}_excerpt"] = hits[0].get("excerpt", "")
                if isinstance(step, LlmTransformStep) and isinstance(out, dict):
                    bindings[f"{step.id}_text"] = out.get("text", "")

                traces.append(
                    StepTrace(step_id=step.id, step_type=step.type, output=out)
                )

            ot = definition.output_template
            artifact: Dict[str, Any] = {
                "artifact_type": ot.artifact_type.value,
                "never_send": ot.never_send,
                "body": render_template(ot.body_template, bindings),
            }
            if ot.subject_template:
                artifact["subject"] = render_template(ot.subject_template, bindings)

            if (
                ot.artifact_type is ArtifactType.EMAIL_DRAFT
                and artifact.get("never_send") is not True
            ):
                raise PermissionError("never_send_v1: refusing to emit sendable email artifact")

            return ProcessRunResult(
                process_id=definition.id,
                version=definition.version,
                ok=True,
                artifact=artifact,
                steps=traces,
            )
        except Exception as exc:  # noqa: BLE001 — dry-run surfaces errors in result
            return ProcessRunResult(
                process_id=definition.id,
                version=definition.version,
                ok=False,
                artifact={},
                steps=[],
                error=f"{type(exc).__name__}: {exc}",
            )


def dry_run(
    definition: ProcessDefinition,
    inputs: Mapping[str, Any] | None = None,
    *,
    runner: Optional[ProcessRunner] = None,
) -> ProcessRunResult:
    """Execute with mock clients (default). Safe for local smoke tests."""
    return (runner or ProcessRunner()).run(definition, inputs)


# Keep ProcessInput referenced for type checkers / re-exports in docs.
_InputType = ProcessInput
