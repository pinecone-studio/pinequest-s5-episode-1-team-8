import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { TrainingManager } from "@/components/training/TrainingManager";
import { apiGet } from "@/lib/api";
import { requireAdmin } from "@/lib/session";
import type { TrainingAnswers, TrainingStatus } from "@/lib/types";

export const metadata: Metadata = { title: "AI сургалт" };
export default async function TrainPage() {
  await requireAdmin();
  const [status, answers] = await Promise.all([apiGet<TrainingStatus>("/api/train"), apiGet<TrainingAnswers>("/api/train/answers")]);
  return <><PageHeader title="AI сургалт" sub="Бэлэн аудиогоос сонгож AI-г жишээн дээр сургана. Бодит дуудлагын асуултад зөв хариултыг заагаад эндээс сургалтаа ажиллуулна." /><TrainingManager initial={status} answers={answers} /></>;
}
