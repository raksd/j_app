export type WorkMode = "remote" | "hybrid" | "onsite" | "any" | "unknown";

export const APPLICATION_STATUSES = [
  "Applied",
  "Interview",
  "Offer",
  "Rejected",
  "No Response",
  "Withdrawn",
] as const;
export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number];

export interface Job {
  id: string;
  source: string;
  title: string;
  company: string;
  location: string;
  work_mode: WorkMode;
  description: string;
  url: string;
  posted_date?: string | null;
  salary?: string | null;
}

export interface ExperienceItem {
  title: string;
  company: string;
  location: string;
  start: string;
  end: string;
  bullets: string[];
}

export interface EducationItem {
  qualification: string;
  institution: string;
  start: string;
  end: string;
  details: string;
}

export interface ProjectItem {
  name: string;
  description: string;
  bullets: string[];
}

export interface StructuredCV {
  full_name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  summary: string;
  skills: string[];
  experience: ExperienceItem[];
  education: EducationItem[];
  certifications: string[];
  projects: ProjectItem[];
}

export interface ScoreResult {
  ats_score: number;
  keyword_score: number;
  llm_score: number;
  matched_keywords: string[];
  missing_requirements: string[];
  rationale: string;
}

export interface TailoredCV {
  cv: StructuredCV;
  docx_path: string;
  changes: string[];
}

export interface CoverLetter {
  text: string;
  docx_path: string;
}

export interface PreparedApplication {
  job: Job;
  score: ScoreResult;
  tailored_cv: TailoredCV;
  cover_letter: CoverLetter;
}

export interface ApplicationRecord {
  id: string;
  date_applied: string;
  company: string;
  job_title: string;
  location: string;
  work_mode: WorkMode;
  job_url: string;
  ats_score: number;
  requirements_not_matched: string[];
  cv_file: string;
  cover_letter_file: string;
  status: ApplicationStatus;
  notes: string;
  last_updated: string;
}
