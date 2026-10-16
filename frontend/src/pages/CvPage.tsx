import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api";
import type { StructuredCV } from "../types";

export default function CvPage() {
  const [cv, setCv] = useState<StructuredCV | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .getCv()
      .then(setCv)
      .catch((err: ApiError) => {
        if (err.status !== 404) setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose a .docx file first.");
      return;
    }
    setError("");
    setUploading(true);
    try {
      setCv(await api.uploadCv(file));
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <section>
      <h2>Your CV</h2>
      <form onSubmit={upload} className="card row">
        <label htmlFor="cv-file">CV file (.docx)</label>
        <input id="cv-file" type="file" accept=".docx" ref={fileRef} />
        <button type="submit" disabled={uploading}>
          {uploading ? "Reading your CV..." : cv ? "Replace CV" : "Upload CV"}
        </button>
      </form>
      <p className="muted">Reading a CV uses your Claude login and can take up to a minute.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {loading && <p>Loading...</p>}
      {!loading && !cv && !error && <p>No CV uploaded yet.</p>}
      {cv && <CvView cv={cv} />}
    </section>
  );
}

function CvView({ cv }: { cv: StructuredCV }) {
  const contact = [cv.email, cv.phone, cv.location].filter(Boolean).join(" | ");
  return (
    <div className="card">
      <h3>{cv.full_name || "(name not found)"}</h3>
      {cv.headline && <p>{cv.headline}</p>}
      {contact && <p className="muted">{contact}</p>}
      {cv.summary && <p>{cv.summary}</p>}

      <h4>Skills ({cv.skills.length})</h4>
      {cv.skills.length ? (
        <ul className="chips">
          {cv.skills.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">No skills found.</p>
      )}

      <h4>Experience ({cv.experience.length})</h4>
      {cv.experience.map((x, i) => (
        <div key={i} className="item">
          <strong>{x.title}</strong>, {x.company}
          <div className="muted">{[x.location, [x.start, x.end].filter(Boolean).join(" - ")].filter(Boolean).join(" | ")}</div>
          <ul>
            {x.bullets.map((b, j) => (
              <li key={j}>{b}</li>
            ))}
          </ul>
        </div>
      ))}

      {cv.projects.length > 0 && (
        <>
          <h4>Projects ({cv.projects.length})</h4>
          {cv.projects.map((p, i) => (
            <div key={i} className="item">
              <strong>{p.name}</strong>
              {p.description && <div>{p.description}</div>}
              <ul>
                {p.bullets.map((b, j) => (
                  <li key={j}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}

      {cv.education.length > 0 && (
        <>
          <h4>Education</h4>
          {cv.education.map((e, i) => (
            <div key={i} className="item">
              <strong>{e.qualification}</strong>, {e.institution}
              <div className="muted">{[e.start, e.end].filter(Boolean).join(" - ")}</div>
            </div>
          ))}
        </>
      )}

      {cv.certifications.length > 0 && (
        <>
          <h4>Certifications</h4>
          <ul>
            {cv.certifications.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
