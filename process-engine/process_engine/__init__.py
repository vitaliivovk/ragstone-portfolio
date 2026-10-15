"""Office IDE process/workflow engine (Phase 4 scaffolding)."""

from process_engine.catalog import ProcessCatalog, ProcessNotFound, load_process
from process_engine.runner import ProcessRunResult, ProcessRunner, dry_run
from process_engine.schema import ProcessDefinition, validate_process_dict

__all__ = [
    "ProcessCatalog",
    "ProcessDefinition",
    "ProcessNotFound",
    "ProcessRunResult",
    "ProcessRunner",
    "dry_run",
    "load_process",
    "validate_process_dict",
]

__version__ = "0.1.0"
