import { useState } from "react";
import { JobList } from "./components/JobList";
import { useJobs } from "./jobs";
import { EditPage } from "./pages/EditPage";
import { GeneratePage } from "./pages/GeneratePage";
import { TrainPage } from "./pages/TrainPage";
import { useAuth } from "./useAuth";

type Tab = "edit" | "train" | "generate";

const TABS: { key: Tab; label: string }[] = [
  { key: "edit", label: "Edit" },
  { key: "train", label: "Train LoRA" },
  { key: "generate", label: "Generate" },
];

export function App() {
  const { user, loading, error } = useAuth();
  const [tab, setTab] = useState<Tab>("edit");
  const jobs = useJobs(user?.uid ?? null);

  if (loading) return <Centered>Signing in…</Centered>;
  if (error) return <Centered>Auth error: {error}</Centered>;
  if (!user) return <Centered>No user.</Centered>;

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Photonome workers</h1>
        <p className="text-sm text-slate-500">
          Signed in as <span className="font-mono">{user.uid}</span> (anonymous)
        </p>
      </header>

      <nav className="flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-violet-600 text-violet-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <section className="rounded border border-slate-200 bg-white p-4 shadow-sm">
        {tab === "edit" && <EditPage userId={user.uid} />}
        {tab === "train" && <TrainPage userId={user.uid} />}
        {tab === "generate" && <GeneratePage userId={user.uid} />}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Recent jobs</h2>
        <JobList jobs={jobs} />
      </section>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center text-sm text-slate-600">{children}</div>
  );
}
