from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    brightdata_api_token: str = ""
    brightdata_transport: Literal["cli", "http"] = "cli"
    brightdata_http_base: str = "https://api.brightdata.com"
    brightdata_cli_timeout_s: float = 240.0
    brightdata_http_timeout_s: float = 240.0
    brightdata_poll_interval_s: float = 5.0

    cna_discovery_collector: str = "c_mt5waa7y28okohy2bb"
    cna_article_collector: str = "c_mt5xrjlvou8e3hv9h"
    edge_discovery_collector: str = "c_mt5x5mxs1yk83lb2ss"
    edge_article_collector: str = "c_mt5xjcc52lzzkhyte1"
    vir_discovery_collector: str = "c_mt5x1ux81pzkfi3gzf"
    vir_article_collector: str = "c_mt5xxz1h12rsttjaza"

    database_url: str = "sqlite:///./causalens.db"
    use_cached_demo_on_failure: bool = True
    frontend_dir: str = ""
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    article_concurrency: int = 3
    max_articles_per_source: int = 5
    gdelt_max_records: int = 30
    gdelt_timeout_s: float = 90.0
    # Primary discovery is Web NGrams + TOC. "doc" keeps the old DOC 2.0 API.
    gdelt_discovery_mode: Literal["ngrams", "doc"] = "ngrams"
    gdelt_doc_fallback: bool = False
    gdelt_ngram_base_url: str = (
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv5/weblegacy/ngrams"
    )
    gdelt_cache_dir: str = "./data/gdelt"
    gdelt_ngram_lookback_hours: int = 6
    gdelt_ngram_lag_minutes: int = 5
    gdelt_ngram_max_snapshots: int = 3
    gdelt_ngram_max_probe_minutes: int = 120
    gdelt_ngram_english_only: bool = True
    gdelt_ngram_min_relevance_score: float = 8.0
    min_brightdata_relevance_score: float = 12.0
    gdelt_brightdata_max_urls: int = 8
    llm_timeout_s: float = 90.0
    llm_temperature: float = 0.0

    @property
    def cors_origin_list(self) -> list[str]:
        items = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if "*" in items:
            return ["*"]
        return items

    @property
    def effective_brightdata_transport(self) -> Literal["cli", "http"]:
        if self.brightdata_transport == "http" and not self.brightdata_api_token:
            return "cli"
        return self.brightdata_transport


@lru_cache
def get_settings() -> Settings:
    return Settings()
