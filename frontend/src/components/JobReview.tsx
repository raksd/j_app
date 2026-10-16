import { useEffect, useRef, useState } from "react";
import { api, fileUrl } from "../api";
import type { ApplicationRecord, Job, PreparedApplication } from "../types";
import ScoreBadge from "./ScoreBadge";

export default function JobReview({ job }: { job: Job }) {
  const [prepared, setPrepared] = useState<PreparedApplication | null>(null);
  const [letter, setLetter] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [logging, setLogging] = useState(false);
  const [record, setRecord] = useState<ApplicationRecord | null>(null);
  const [error, setError] = useState("");
  const submitting = useRef(false);

  useEffect(() => {
    setPrepared(null);
    setLetter("");
    setRecord(null);
    setError("");
    submitting.current = false;
  }, [job.id]);

  async function prepare() {
    setError("");
    setPreparing(true);
    try {
      const p = await api.prepare(job);
      setPrepared(p);
      setLetter(p.cover_letter.text);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPreparing(false);
    }
  }

  async function markApplied() {
    if (!prepared || submitting.current) return;
    submitting.current = true;
    setError("");
    setLogging(true);
    try {
      setRecord(await api.logApplication(prepared, letter));
    } catch (err) {
      setError((err as Error).message);
      submitting.current = false;
    } finally {
      setLogging(false);
    }
  }

  return (
    <div className="card review">
      <h3>
        {job.title} <span className="muted">at {job.company}</span>
      </h3>
      <p className="muted">
        {[job.location, job.work_mode !== "unknown" ? job.work_mode : "", job.source, job.salary, job.posted_date].filter(Boolean).join(" | ")}
      </p>
      <p>
        <a href={job.url} target="_blank" rel="noreferrer">
          Open the posting
        </a>{" "}
        <span className="muted">(you apply on the employer's site; this app only prepares your CV and letter)</span>
      </p>

      <details open={!prepared}>
        <summary>Job description</summary>
        <pre className="desc">{job.description || "(no description available)"}</pre>
      </details>

      {error && <p className="error" role="alert">{error}</p>}

      {!prepared && (
        <button type="button" onClick={prepare} disabled={preparing}>
          {preparing ? "Scoring, tailoring CV and writing letter (about a minute)..." : "Prepare application"}
        </button>
      )}

      {prepared && (
        <div className="prepared">
          <h4>Match against your CV</h4>
          <div className="scores">
            <div>
              <ScoreBadge score={prepared.score.ats_score} /> ATS score
            </div>
            <div>Keyword score: {prepared.score.keyword_score.toFixed(0)}</div>
            <div>Model score: {prepared.score.llm_score.toFixed(0)}</div>
          </div>
          {prepared.score.rationale && <p>{prepared.score.rationale}</p>}

          <h4>Matched keywords</h4>
          {prepared.score.matched_keywords.length ? (
            <ul className="chips">
              {prepared.score.matched_keywords.map((k) => (
                <li key={k}>{k}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">None.</p>
          )}

          <h4>Requirements not matched in your CV</h4>
          {prepared.score.missing_requirements.length ? (
            <ul className="chips missing">
              {prepared.score.missing_requirements.map((k) => (
                <li key={k}>{k}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">None found.</p>
          )}

          <h4>Tailored CV changes</h4>
          {prepared.tailored_cv.changes.length ? (
            <ul>
              {prepared.tailored_cv.changes.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">No changes were made to your CV.</p>
          )}
          <p>
            <a href={fileUrl(job.id, prepared.tailored_cv.docx_path)}>Download tailored CV (.docx)</a>
          </p>

          <h4>Cover letter</h4>
          <label htmlFor="letter">Edit the letter before you log it. Check every claim is true.</label>
          <textarea id="letter" rows={14} value={letter} onChange={(e) => setLetter(e.target.value)} disabled={!!record} />
          <p>
            <a href={fileUrl(job.id, prepared.cover_letter.docx_path)}>
              {record ? "Download cover letter (.docx, with your edits)" : "Download cover letter (.docx, before your edits)"}
            </a>
          </p>

          {record ? (
            <p className="success" role="status">
              Logged on {record.date_applied}. It is in your tracker (data/tracker.xlsx). Now apply on the employer's site.
            </p>
          ) : (
            <button type="button" onClick={markApplied} disabled={logging || !letter.trim()}>
              {logging ? "Logging..." : "Mark as applied"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
