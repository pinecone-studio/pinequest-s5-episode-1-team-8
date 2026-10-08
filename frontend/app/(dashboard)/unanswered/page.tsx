import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { UnansweredManager } from "@/components/unanswered/UnansweredManager";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { TrainingAnswers, UnansweredReview } from "@/lib/types";

export const metadata: Metadata = { title: "Хариулаагүй асуулт" };

export default async function UnansweredPage() {
  await requireUser();
  const [review, answers] = await Promise.all([
    apiGet<UnansweredReview>("/api/unanswered/review"),
    apiGet<TrainingAnswers>("/api/train/answers").catch(() => null),
  ]);
  return (
    <>
      <PageHeader
        title="Хариулаагүй асуулт"
        sub="AI туслах хариулж чадаагүй асуултад зөв хариултыг сонгох эсвэл шинээр бичнэ."
      />
      <UnansweredManager initial={review} answers={answers} />
    </>
  );
}
