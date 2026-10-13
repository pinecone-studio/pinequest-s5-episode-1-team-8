"use client";

import { useState, useEffect, useMemo } from "react";

import { BuildPanel } from "@/components/knowledge/BuildPanel";
import { ActionStatus } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Tag } from "@/components/ui/Tag";
import { apiSend } from "@/lib/client";
import type { FaqData, FaqItem } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function FaqEditor({ initial }: { initial: FaqData }) {
  const [greeting, setGreeting] = useState(initial.greeting);
  const [items, setItems] = useState(initial.faq);
  const [searchQuery, setSearchQuery] = useState("");
  const [onlyTodo, setOnlyTodo] = useState(false);
  const [deleteIndex, setDeleteIndex] = useState<number | null>(null);
  const [duplicateMessage, setDuplicateMessage] = useState<string | null>(null);

  const { pending, error, message, run } = useAction();

  useEffect(() => {
    if (!duplicateMessage) return;
    const timer = setTimeout(() => setDuplicateMessage(null), 3000);
    return () => clearTimeout(timer);
  }, [duplicateMessage]);

  const update = (index: number, patch: Partial<FaqItem>) =>
    setItems((rows) =>
      rows.map((row, current) =>
        current === index ? { ...row, ...patch } : row
      )
    );

  function duplicateItem(index: number) {
    setItems((rows) => {
      const target = rows[index];
      const duplicated: FaqItem = {
        id: `faq_${Date.now() % 100000}_copy`,
        questions: [...target.questions],
        answer: target.answer,
        ...(target.auto !== undefined ? { auto: target.auto } : {}),
      };
      const nextRows = [...rows];
      nextRows.splice(index + 1, 0, duplicated);
      return nextRows;
    });
    setDuplicateMessage("Хувиллаа. Хадгалах товчийг дарна уу.");
  }

  function save() {
    const faq = items
      .map((row) => ({
        ...row,
        id: row.id.trim(),
        answer: row.answer.trim(),
        questions: row.questions
          .map((question) => question.trim())
          .filter(Boolean),
      }))
      .filter((row) => row.id && row.answer && row.questions.length);

    void run(
      () =>
        apiSend("/api/faq", "PUT", {
          ...initial,
          greeting: greeting.trim(),
          faq,
        }),
      "Хадгаллаа. Аудио бэлдэх дарна уу ✓"
    );
  }

  function confirmDelete() {
    if (deleteIndex !== null) {
      setItems((rows) => rows.filter((_, i) => i !== deleteIndex));
      setDeleteIndex(null);
    }
  }

  // Хайлт болон TODO шүүлтүүрийн логик (originalIndex-ийг хамт хадгална)
  const filteredItems = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();

    return items
      .map((item, originalIndex) => ({ item, originalIndex }))
      .filter(({ item }) => {
        // Зөвхөн TODO шүүлтүүр шалгах (хариулт эсвэл бусад нөхцөлд TODO байгаа эсэх)
        const isTodoItem =
          item.answer.includes("TODO") || (item as any).isTodo;
        if (onlyTodo && !isTodoItem) {
          return false;
        }

        if (!query) return true;

        const matchId = item.id.toLowerCase().includes(query);
        const matchAnswer = item.answer.toLowerCase().includes(query);
        const matchQuestions = item.questions.some((q) =>
          q.toLowerCase().includes(query)
        );

        return matchId || matchAnswer || matchQuestions;
      });
  }, [items, searchQuery, onlyTodo]);

  return (
    <div className="space-y-7">
      <div className="flex items-center justify-between">
        {duplicateMessage && (
          <span className="text-sm font-medium text-brand animate-pulse">
            {duplicateMessage}
          </span>
        )}
        <div className="ml-auto flex items-center gap-3">
          <Button variant="primary" size="lg" onClick={save} disabled={pending}>
            Хадгалах
          </Button>
        </div>
      </div>

      <section className="rounded-[14px] bg-panel px-[22px] py-5">
        <label className="mb-2 block text-sm text-muted">Мэндчилгээ</label>

        <input
          className="w-full rounded-[10px] border border-line-2 bg-bg px-4 py-3 outline-none focus:border-brand"
          value={greeting}
          onChange={(event) => setGreeting(event.target.value)}
        />

        <div className="mt-6 mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-fg">
            Харагдаж буй {filteredItems.length} / Нийт {items.length} FAQ
          </h2>

          {/* Хайлт болон TODO шүүлтүүр хэсэг */}
          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            <input
              className="w-full sm:w-[260px] rounded-[10px] border border-line-2 bg-bg px-3 py-2 text-sm outline-none focus:border-brand"
              placeholder="ID, асуулт эсвэл хариултаар хайх..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-fg">
              <input
                type="checkbox"
                checked={onlyTodo}
                onChange={(e) => setOnlyTodo(e.target.checked)}
                className="w-4 h-4 rounded border-line-2"
              />
              Зөвхөн TODO
            </label>
          </div>
        </div>

        {items.length === 0 ? (
          <div className="mt-5 rounded-[10px] border border-line-2 bg-bg px-5 py-8 text-center">
            <p className="text-sm text-muted">
              Одоогоор FAQ алга. + FAQ нэмэх товчийг дарна уу.
            </p>

            <Button
              className="mt-4"
              onClick={() =>
                setItems((rows) => [
                  ...rows,
                  {
                    id: `faq_${Date.now() % 100000}`,
                    questions: [""],
                    answer: "",
                  },
                ])
              }
            >
              + FAQ нэмэх
            </Button>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="mt-5 rounded-[10px] border border-line-2 bg-bg px-5 py-8 text-center">
            <p className="text-sm text-muted">Тохирох FAQ олдсонгүй</p>
          </div>
        ) : (
          <div className="mt-6 divide-y divide-line">
            {filteredItems.map(({ item, originalIndex }) => (
              <div key={`${item.id}-${originalIndex}`} className="py-5 first:pt-0">
                <div className="mb-3 flex flex-wrap items-center gap-3">
                  <input
                    className="w-[260px] rounded-[10px] border border-line-2 bg-bg px-3 py-2 font-mono text-sm outline-none focus:border-brand"
                    value={item.id}
                    onChange={(event) =>
                      update(originalIndex, {
                        id: event.target.value,
                      })
                    }
                  />

                  {item.answer.includes("TODO") && (
                    <Tag tone="warn">TODO — алгасна</Tag>
                  )}

                  {item.auto && <Tag tone="gray">автомат</Tag>}

                  <div className="ml-auto flex items-center gap-2">
                    <Button
                      onClick={() => duplicateItem(originalIndex)}
                      title="Энэ FAQ-г хувилах"
                    >
                      Хувилах
                    </Button>
                    <Button
                      className="text-danger"
                      onClick={() => setDeleteIndex(originalIndex)}
                    >
                      Устгах
                    </Button>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <label className="text-sm text-muted">
                    Асуултууд (мөр бүрд нэг)
                    <textarea
                      className="mt-2 min-h-32 w-full rounded-[10px] border border-line-2 bg-bg p-3 text-fg outline-none focus:border-brand"
                      value={item.questions.join("\n")}
                      onChange={(event) =>
                        update(originalIndex, {
                          questions: event.target.value.split("\n"),
                        })
                      }
                    />
                  </label>

                  <label className="text-sm text-muted">
                    Хариулт
                    <textarea
                      className="mt-2 min-h-32 w-full rounded-[10px] border border-line-2 bg-bg p-3 text-fg outline-none focus:border-brand"
                      value={item.answer}
                      onChange={(event) =>
                        update(originalIndex, {
                          answer: event.target.value,
                        })
                      }
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          {items.length > 0 && (
            <Button
              onClick={() =>
                setItems((rows) => [
                  ...rows,
                  {
                    id: `faq_${Date.now() % 100000}`,
                    questions: [""],
                    answer: "",
                  },
                ])
              }
            >
              + FAQ нэмэх
            </Button>
          )}

          <Button variant="primary" onClick={save} disabled={pending}>
            Хадгалах
          </Button>

          <ActionStatus error={error} message={message} />
        </div>
      </section>

      <BuildPanel />

      <ConfirmDialog
        open={deleteIndex !== null}
        title="FAQ устгах"
        description="Энэ FAQ-г устгахдаа итгэлтэй байна уу? Энэ үйлдлийг буцаах боломжгүй."
        confirmLabel="Устгах"
        cancelLabel="Цуцлах"
        danger={true}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteIndex(null)}
      />
    </div>
  );
}