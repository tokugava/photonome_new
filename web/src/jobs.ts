import { collection, limit, onSnapshot, orderBy, query, where } from "firebase/firestore";
import { httpsCallable } from "firebase/functions";
import { useEffect, useState } from "react";
import { db, functions } from "./firebase";
import type { EditParams, GenerateParams, JobDoc, TrainParams } from "./types";

type SubmitResponse = { jobId: string };

export const submitEditJob = httpsCallable<EditParams, SubmitResponse>(functions, "submitEditJob");
export const submitTrainJob = httpsCallable<TrainParams, SubmitResponse>(functions, "submitTrainJob");
export const submitGenerateJob = httpsCallable<GenerateParams, SubmitResponse>(functions, "submitGenerateJob");

export function useJobs(userId: string | null, max = 20) {
  const [jobs, setJobs] = useState<JobDoc[]>([]);
  useEffect(() => {
    if (!userId) return;
    const q = query(
      collection(db, "jobs"),
      where("userId", "==", userId),
      orderBy("createdAt", "desc"),
      limit(max),
    );
    const unsub = onSnapshot(q, (snap) => {
      setJobs(snap.docs.map((d) => ({ jobId: d.id, ...(d.data() as Omit<JobDoc, "jobId">) })));
    });
    return unsub;
  }, [userId, max]);
  return jobs;
}
