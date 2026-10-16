import type {
  ApplicationRecord,
  ApplicationStatus,
  Job,
  PreparedApplication,
  StructuredCV,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const parts = detail.map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""));
      const joined = parts.filter(Boolean).join("; ");
      if (joined) return joined;
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is it running on port 8000?");
  }
  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    throw new ApiError(res.status, detailMessage(body, `Request failed (${res.status})`));
  }
  return body as T;
}

function json(method: string, data: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) };
}

export const api = {
  getCv: () => request<StructuredCV>("/cv"),
  uploadCv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<StructuredCV>("/cv/upload", { method: "POST", body: form });
  },

  fromUrl: (body: { url: string; title?: string; company?: string; description?: string }) =>
    request<Job>("/jobs/from-url", json("POST", body)),
  prepare: (job: Job) => request<PreparedApplication>("/jobs/prepare", json("POST", { job })),

  logApplication: (prepared: PreparedApplication, coverLetterText: string) =>
    request<ApplicationRecord>("/applications", json("POST", { prepared, cover_letter_text: coverLetterText })),
  listApplications: () => request<ApplicationRecord[]>("/applications"),
  updateStatus: (id: string, status: ApplicationStatus, notes?: string) =>
    request<ApplicationRecord>(`/applications/${id}/status`, json("PATCH", { status, notes })),
};

export function fileUrl(jobId: string, path: string): string {
  const name = path.split(/[\\/]/).pop() ?? path;
  return `/api/files/${encodeURIComponent(jobId)}/${encodeURIComponent(name)}`;
}
