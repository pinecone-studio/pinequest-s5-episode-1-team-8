import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { UnansweredManager } from "@/components/unanswered/UnansweredManager";
import { apiGet } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { TrainingAnswers, UnansweredReview } from "@/lib/types";

export const metadata: Metadata = { title: "Хариулж чадаагүй" };

export default async function UnansweredPage() {
  await requireUser();
  const [review, answers] = await Promise.all([
    apiGet<UnansweredReview>("/api/unanswered/review"),
    apiGet<TrainingAnswers>("/api/train/answers").catch(() => null),
  ]);
  return (
    <>
      <PageHeader
        title="Хариулж чадаагүй"
        sub="Бодит дуудлагын асуултыг AI одоо хэрхэн хариулахыг дахин шалгана. Шийдэгдээгүй асуултад байгаа хариултыг заах эсвэл шинэ хариулт бичээд аудио, сургалтыг хамтад нь бэлдэнэ."
      />
      <UnansweredManager initial={review} answers={answers} />
    </>
  );
}
