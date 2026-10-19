from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field

WorkMode = Literal["remote", "hybrid", "onsite", "any", "unknown"]

FOLLOW_UP_AFTER_DAYS = 7


class ApplicationStatus(str, Enum):
    APPLIED = "Applied"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"
    NO_RESPONSE = "No Response"
    WITHDRAWN = "Withdrawn"


class Job(BaseModel):
    id: str
    source: str
    title: str
    company: str
    location: str = ""
    work_mode: WorkMode = "unknown"
    description: str = ""
    url: str
    posted_date: Optional[date] = None
    salary: Optional[str] = None


class ExperienceItem(BaseModel):
    title: str
    company: str
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    qualification: str
    institution: str
    start: str = ""
    end: str = ""
    details: str = ""


class ProjectItem(BaseModel):
    name: str
    description: str = ""
    bullets: list[str] = Field(default_factory=list)


class StructuredCV(BaseModel):
    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = Field(default_factory=list)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)


class ScoreResult(BaseModel):
    ats_score: float = Field(ge=0, le=100)
    keyword_score: float = Field(ge=0, le=100)
    llm_score: float = Field(ge=0, le=100)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    rationale: str = ""


class TailoredCV(BaseModel):
    cv: StructuredCV
    docx_path: str
    changes: list[str] = Field(default_factory=list)


class CoverLetter(BaseModel):
    text: str
    docx_path: str


class PreparedApplication(BaseModel):
    job: Job
    score: ScoreResult
    tailored_cv: TailoredCV
    cover_letter: CoverLetter


class ApplicationRecord(BaseModel):
    id: str
    date_applied: date
    company: str
    job_title: str
    location: str = ""
    work_mode: WorkMode = "unknown"
    job_url: str
    ats_score: float
    requirements_not_matched: list[str] = Field(default_factory=list)
    cv_file: str = ""
    cover_letter_file: str = ""
    status: ApplicationStatus = ApplicationStatus.APPLIED
    notes: str = ""
    last_updated: datetime

    @computed_field
    @property
    def follow_up_due(self) -> bool:
        return needs_follow_up(self.status, self.date_applied, date.today())


def needs_follow_up(status: ApplicationStatus, date_applied: date, today: date) -> bool:
    return status == ApplicationStatus.APPLIED and (today - date_applied).days >= FOLLOW_UP_AFTER_DAYS
