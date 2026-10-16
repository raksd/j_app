import { useState } from "react";
import { ApiError, api } from "../api";
import type { Job } from "../types";

export default function AddJobLink({ onAdded }: { onAdded: (job: Job) => void }) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [description, setDescription] = useState("");
  const [needsPaste, setNeedsPaste] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMessage("");
    setBusy(true);
    try {
      const body = needsPaste
        ? { url: url.trim(), title: title.trim(), company: company.trim(), description: description.trim() }
        : { url: url.trim() };
      const job = await api.fromUrl(body);
      onAdded(job);
      setUrl("");
      setTitle("");
      setCompany("");
      setDescription("");
      setNeedsPaste(false);
    } catch (err) {
      const e2 = err as ApiError;
      setNeedsPaste(e2.status === 422 || needsPaste);
      setMessage(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card grid" aria-label="Add a job link">
      <h3>Add a job link</h3>
      <p className="muted">
        Found a job on LinkedIn, Indeed or a careers page? Paste the link. The app reads the page itself and never logs in to any site.
      </p>
      <label htmlFor="job-url">Job link</label>
      <input id="job-url" type="url" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />

      {needsPaste && (
        <>
          <p className="warn" role="alert">
            {message || "The page could not be read."} Paste the job details below; the link stays attached.
          </p>
          <label htmlFor="job-title">Job title</label>
          <input id="job-title" required value={title} onChange={(e) => setTitle(e.target.value)} />
          <label htmlFor="job-company">Company</label>
          <input id="job-company" required value={company} onChange={(e) => setCompany(e.target.value)} />
          <label htmlFor="job-desc">Job description (copy the text from the posting)</label>
          <textarea id="job-desc" required rows={8} value={description} onChange={(e) => setDescription(e.target.value)} />
        </>
      )}
      {!needsPaste && message && <p className="error" role="alert">{message}</p>}

      <div className="row">
        <button type="submit" disabled={busy}>
          {busy ? "Working..." : needsPaste ? "Use pasted details" : "Add job"}
        </button>
        {needsPaste && (
          <button type="button" className="secondary" onClick={() => { setNeedsPaste(false); setMessage(""); }}>
            Try the link again
          </button>
        )}
      </div>
    </form>
  );
}
