import { useState } from "react";
import AddJobLink from "../components/AddJobLink";
import JobReview from "../components/JobReview";
import type { Job } from "../types";

export default function AddJobPage() {
  const [job, setJob] = useState<Job | null>(null);

  return (
    <section>
      <h2>Add a job</h2>
      <AddJobLink onAdded={setJob} />
      {job && <JobReview job={job} />}
    </section>
  );
}
