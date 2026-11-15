from typing import Any
from pydantic import BaseModel, Field

class CandidateProfile(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    headline: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)

class ConfirmProfileRequest(BaseModel):
    profile: CandidateProfile
    resume_id: str

class KnowledgeCreate(BaseModel):
    question: str
    answer: str
    category: str = "general"
    reusable: bool = True

class KnowledgeUpdate(BaseModel):
    answer: str | None = None
    category: str | None = None
    reusable: bool | None = None
