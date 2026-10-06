import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { TrainingManager } from "@/components/training/TrainingManager";
import { apiGet } from "@/lib/api";
import type { TrainingAnswers, TrainingStatus } from "@/lib/types";

export const metadata: Metadata = { title: "AI сургалт" };
export default async function TrainPage() {
  const [status, answers] = await Promise.all([apiGet<TrainingStatus>("/api/train"), apiGet<TrainingAnswers>("/api/train/answers")]);
  return <><PageHeader title="AI сургалт" sub="Залгагчийн бодит асуултыг зөв FAQ эсвэл мэдээлэлтэй холбож сургана." /><TrainingManager initial={status} answers={answers} /></>;
}
