from __future__ import annotations


class CausaLensError(Exception):
    """Base application error with a stable public code."""

    code = "CAUSALENS_ERROR"
    status_code = 500

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class BrightDataTimeout(CausaLensError):
    code = "BRIGHTDATA_TIMEOUT"
    status_code = 504


class BrightDataParseError(CausaLensError):
    code = "BRIGHTDATA_PARSE_ERROR"
    status_code = 502


class BrightDataUnavailable(CausaLensError):
    code = "BRIGHTDATA_UNAVAILABLE"
    status_code = 502


class GDELTUnavailable(CausaLensError):
    code = "GDELT_UNAVAILABLE"
    status_code = 502


class LLMExtractionError(CausaLensError):
    code = "LLM_EXTRACTION_ERROR"
    status_code = 502


class AnalysisNotFound(CausaLensError):
    code = "ANALYSIS_NOT_FOUND"
    status_code = 404


class EventNotFound(CausaLensError):
    code = "EVENT_NOT_FOUND"
    status_code = 404


class SourceNotFound(CausaLensError):
    code = "SOURCE_NOT_FOUND"
    status_code = 404
