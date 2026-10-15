import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BotConfig:
    """Bot Framework configuration."""

    app_id: str
    app_password: str
    app_type: str = "SingleTenant"


@dataclass(frozen=True)
class OpenAIConfig:
    """OpenAI configuration."""

    api_key: str
    model: str = "gpt-5-mini"
    optimizer_model: str = "gpt-5-nano"
    embedding_model: str = "text-embedding-3-small"
    #: Upper bound on completion tokens for the answer model (reduces mid-sentence cutoffs).
    max_completion_tokens: int = 32768


@dataclass(frozen=True)
class PineconeConfig:
    """Pinecone configuration."""

    api_key: str
    index_name: str
    namespace: str = "v3"


@dataclass(frozen=True)
class StorageConfig:
    """Azure Storage configuration for conversation memory."""

    connection_string: Optional[str] = None
    history_limit_default: int = 50
    history_cache_ttl_seconds: float = 30.0
    history_cache_max_users: int = 256
    #: Purge conversation rows older than this many hours (0 = disabled). Timer trigger uses this.
    history_ttl_hours: float = 24.0
    #: Purge RAG context cache rows older than this many hours (0 = disabled).
    context_cache_ttl_hours: float = 6.0

    @property
    def enabled(self) -> bool:
        """Check if storage is configured."""
        return bool(self.connection_string)


def _pinecone_index_from_env() -> str:
    """Prefer PINECONE_INDEX_NAME; PINECONE_INDEX is legacy / Terraform alias."""
    for env_key in ("PINECONE_INDEX_NAME", "PINECONE_INDEX"):
        raw = os.environ.get(env_key, "").strip()
        if raw:
            return raw
    return "text-embedding-3-small"


def _storage_config_from_env(connection_string: Optional[str]) -> StorageConfig:
    if connection_string is None or not str(connection_string).strip():
        return StorageConfig()
    raw_limit = os.environ.get("HISTORY_MESSAGE_LIMIT", "50").strip()
    history_limit_default = int(raw_limit) if raw_limit else 50
    raw_ttl = os.environ.get("HISTORY_CACHE_TTL_SECONDS", "30").strip()
    history_cache_ttl_seconds = float(raw_ttl) if raw_ttl else 30.0
    raw_max = os.environ.get("HISTORY_CACHE_MAX_USERS", "256").strip()
    history_cache_max_users = int(raw_max) if raw_max else 256
    raw_hist_ttl = os.environ.get("HISTORY_TTL_HOURS", "24").strip()
    history_ttl_hours = float(raw_hist_ttl) if raw_hist_ttl else 24.0
    raw_ctx_ttl = os.environ.get("CONTEXT_CACHE_TTL_HOURS", "6").strip()
    context_cache_ttl_hours = float(raw_ctx_ttl) if raw_ctx_ttl else 6.0
    return StorageConfig(
        connection_string=str(connection_string).strip(),
        history_limit_default=history_limit_default,
        history_cache_ttl_seconds=history_cache_ttl_seconds,
        history_cache_max_users=history_cache_max_users,
        history_ttl_hours=history_ttl_hours,
        context_cache_ttl_hours=context_cache_ttl_hours,
    )


@dataclass(frozen=True)
class AppConfig:
    """Application configuration."""

    bot: BotConfig
    openai: OpenAIConfig
    pinecone: PineconeConfig
    storage: StorageConfig


def _max_completion_tokens_from_env() -> int:
    raw = os.environ.get("OPENAI_MAX_COMPLETION_TOKENS", "32768").strip()
    if not raw:
        return 32768
    parsed = int(raw)
    if parsed < 1:
        raise ValueError("OPENAI_MAX_COMPLETION_TOKENS must be >= 1")
    return parsed


def load_rag_stack_settings() -> tuple[OpenAIConfig, PineconeConfig, StorageConfig]:
    """
    OpenAI + Pinecone + optional Table Storage only (no Bot Framework credentials).

    Use for local scripts that exercise the same RAG code path as Azure Functions.
    """
    openai_cfg = OpenAIConfig(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
        optimizer_model=os.environ.get("OPENAI_OPTIMIZER_MODEL", "gpt-5-nano"),
        embedding_model=os.environ.get(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        ),
        max_completion_tokens=_max_completion_tokens_from_env(),
    )
    pinecone_cfg = PineconeConfig(
        api_key=os.environ["PINECONE_API_KEY"],
        index_name=_pinecone_index_from_env(),
        namespace=os.environ.get("PINECONE_NAMESPACE", "v3"),
    )
    storage_cs = os.environ.get(
        "AZURE_STORAGE_CONNECTION_STRING",
        os.environ.get("AzureWebJobsStorage"),
    )
    if storage_cs is not None and not storage_cs.strip():
        storage_cs = None
    storage_cfg = _storage_config_from_env(storage_cs)
    return openai_cfg, pinecone_cfg, storage_cfg


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    storage_cs = os.environ.get(
        "AZURE_STORAGE_CONNECTION_STRING",
        os.environ.get("AzureWebJobsStorage"),
    )
    if storage_cs is not None and not storage_cs.strip():
        storage_cs = None
    return AppConfig(
        bot=BotConfig(
            app_id=os.environ["MICROSOFT_APP_ID"],
            app_password=os.environ["MICROSOFT_APP_PASSWORD"],
            app_type=os.environ.get("MICROSOFT_APP_TYPE", "SingleTenant"),
        ),
        openai=OpenAIConfig(
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
            optimizer_model=os.environ.get("OPENAI_OPTIMIZER_MODEL", "gpt-5-nano"),
            embedding_model=os.environ.get(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            max_completion_tokens=_max_completion_tokens_from_env(),
        ),
        pinecone=PineconeConfig(
            api_key=os.environ["PINECONE_API_KEY"],
            index_name=_pinecone_index_from_env(),
            namespace=os.environ.get("PINECONE_NAMESPACE", "v3"),
        ),
        storage=_storage_config_from_env(storage_cs),
    )
