import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import ScoreBadge from "../components/ScoreBadge";
import { APPLICATION_STATUSES, type ApplicationRecord, type ApplicationStatus } from "../types";

export default function TrackerPage() {
  const [records, setRecords] = useState<ApplicationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "">("");
  const [newestFirst, setNewestFirst] = useState(true);
  const [notesDraft, setNotesDraft] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState("");

  useEffect(() => {
    api
      .listApplications()
      .then(setRecords)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => {
    const q = text.trim().toLowerCase();
    const rows = records.filter(
      (r) =>
        (!statusFilter || r.status === statusFilter) &&
        (!q || `${r.company} ${r.job_title} ${r.notes}`.toLowerCase().includes(q)),
    );
    rows.sort((a, b) => (newestFirst ? -1 : 1) * a.date_applied.localeCompare(b.date_applied) || (newestFirst ? -1 : 1) * a.last_updated.localeCompare(b.last_updated));
    return rows;
  }, [records, text, statusFilter, newestFirst]);

  async function save(r: ApplicationRecord, status: ApplicationStatus, notes: string) {
    setError("");
    setSavingId(r.id);
    try {
      const updated = await api.updateStatus(r.id, status, notes);
      setRecords((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      setNotesDraft((d) => {
        const { [r.id]: _drop, ...rest } = d;
        return rest;
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingId("");
    }
  }

  return (
    <section>
      <h2>Applications</h2>
      <p className="muted">
        Saved in <code>data/tracker.xlsx</code>. You can open that file in Excel, but close it before changing a status here.
      </p>

      <div className="card row">
        <label htmlFor="t-text">Search</label>
        <input id="t-text" value={text} onChange={(e) => setText(e.target.value)} placeholder="company, title or notes" />
        <label htmlFor="t-status">Status</label>
        <select id="t-status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as ApplicationStatus | "")}>
          <option value="">All</option>
          {APPLICATION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button type="button" className="secondary" onClick={() => setNewestFirst((v) => !v)}>
          Date applied: {newestFirst ? "newest first" : "oldest first"}
        </button>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {loading && <p>Loading...</p>}
      {!loading && records.length === 0 && !error && <p>No applications logged yet.</p>}
      {!loading && records.length > 0 && visible.length === 0 && <p>No applications match the filters.</p>}

      {visible.length > 0 && (
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Date applied</th>
                <th>Company</th>
                <th>Job title</th>
                <th>Work mode</th>
                <th>ATS</th>
                <th>Requirements not matched</th>
                <th>Status</th>
                <th>Notes</th>
                <th>Last updated</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => {
                const draft = notesDraft[r.id];
                return (
                  <tr key={r.id}>
                    <td>{r.date_applied}</td>
                    <td>{r.company}</td>
                    <td>
                      <a href={r.job_url} target="_blank" rel="noreferrer">
                        {r.job_title}
                      </a>
                    </td>
                    <td>{r.work_mode}</td>
                    <td>
                      <ScoreBadge score={r.ats_score} />
                    </td>
                    <td>{r.requirements_not_matched.join("; ")}</td>
                    <td>
                      <select
                        aria-label={`Status for ${r.job_title} at ${r.company}`}
                        value={r.status}
                        disabled={savingId === r.id}
                        onChange={(e) => save(r, e.target.value as ApplicationStatus, draft ?? r.notes)}
                      >
                        {APPLICATION_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <textarea
                        aria-label={`Notes for ${r.job_title} at ${r.company}`}
                        rows={2}
                        value={draft ?? r.notes}
                        onChange={(e) => setNotesDraft((d) => ({ ...d, [r.id]: e.target.value }))}
                        onBlur={() => {
                          if (draft !== undefined && draft !== r.notes) void save(r, r.status, draft);
                        }}
                      />
                    </td>
                    <td>{r.last_updated.replace("T", " ")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
