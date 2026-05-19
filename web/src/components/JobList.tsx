import { getDownloadURL, ref } from "firebase/storage";
import { useEffect, useState } from "react";
import { storage } from "../firebase";
import type { JobDoc } from "../types";

function useResolvedUrl(outputPath?: string, outputUrl?: string): string | undefined {
  const [resolved, setResolved] = useState<string | undefined>(outputUrl);
  useEffect(() => {
    setResolved(outputUrl);
    if (outputUrl || !outputPath) return;
    getDownloadURL(ref(storage, outputPath))
      .then(setResolved)
      .catch(() => {});
  }, [outputPath, outputUrl]);
  return resolved;
}

const statusStyle: Record<JobDoc["status"], string> = {
  queued: "bg-slate-200 text-slate-700",
  running: "bg-blue-100 text-blue-800",
  success: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
};

function JobRow({ job }: { job: JobDoc }) {
  const url = useResolvedUrl(job.outputPath, job.outputUrl);
  return (
    <li className="rounded border border-slate-200 bg-white p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="font-mono text-xs text-slate-500">{job.jobId}</div>
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${statusStyle[job.status]}`}>
          {job.kind} · {job.status}
        </span>
      </div>
      {job.error && <div className="mt-1 text-red-700">Error: {job.error}</div>}
      {url ? (
        <div className="mt-2">
          <a href={url} target="_blank" rel="noreferrer" className="text-violet-700 hover:underline">
            {job.outputPath}
          </a>
          {job.kind !== "train" && (
            <img
              src={url}
              alt={job.jobId}
              className="mt-2 max-h-64 rounded border border-slate-200"
            />
          )}
        </div>
      ) : job.outputPath ? (
        <div className="mt-1 font-mono text-xs text-slate-600">{job.outputPath}</div>
      ) : null}
    </li>
  );
}

export function JobList({ jobs }: { jobs: JobDoc[] }) {
  if (!jobs.length) {
    return <p className="text-sm text-slate-500">No jobs yet. Submit one above.</p>;
  }
  return (
    <ul className="space-y-2">
      {jobs.map((job) => <JobRow key={job.jobId} job={job} />)}
    </ul>
  );
}
