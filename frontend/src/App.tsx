import { useState } from "react";
import AddJobPage from "./pages/AddJobPage";
import CvPage from "./pages/CvPage";
import TrackerPage from "./pages/TrackerPage";

const TABS = [
  { id: "cv", label: "My CV" },
  { id: "add", label: "Add a job" },
  { id: "tracker", label: "Applications" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<TabId>("cv");
  return (
    <>
      <header>
        <h1>Job Application Assistant</h1>
        <nav aria-label="Main">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? "tab active" : "tab"}
              aria-current={tab === t.id ? "page" : undefined}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        <div hidden={tab !== "cv"}>
          <CvPage />
        </div>
        <div hidden={tab !== "add"}>
          <AddJobPage />
        </div>
        {tab === "tracker" && <TrackerPage />}
      </main>
    </>
  );
}
