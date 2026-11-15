"""Versioned opt-in references. Caller payloads never establish evidence authority."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GitHubFileEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["github_file"]
    path: Annotated[str, Field(min_length=1, max_length=512, pattern=r"^[A-Za-z0-9_./ -]+$")]
    source_revision: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    content_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @field_validator("path")
    @classmethod
    def relative_file(cls, value):
        if any(part in {"", ".", ".."} for part in value.split("/")):
            raise ValueError("An exact relative repository file path is required")
        return value
