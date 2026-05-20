import { getMatchingData, gradeMatching } from "./matching.js";
import {
  getYesNoStatements,
  gradeYesNoAnswer,
  isYesNoQuestion,
} from "./yesno.js";
import type { GradeResult, QuizOption, QuizQuestion } from "./types.js";
import type { YesNoChoice } from "./yesno.js";

/** Lấy danh sách id đáp án đúng (tick xanh trong PDF). */
export function getCorrectOptionIds(question: QuizQuestion): string[] {
  const m = getMatchingData(question);
  if (m) {
    return m.definitions.map((d) => `${d.id}→${m.correctMap[d.id]}`);
  }
  if (isYesNoQuestion(question)) {
    return getYesNoStatements(question).map((s) =>
      s.isCorrect ? `${s.id}:yes` : `${s.id}:no`
    );
  }
  return question.options.filter((o) => o.isCorrect).map((o) => o.id);
}

export function normalizeSelectedIds(selected: string | string[]): string[] {
  const arr = Array.isArray(selected) ? selected : [selected];
  return [...new Set(arr.map((s) => s.trim().toUpperCase()))].sort();
}

function setsEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const sa = [...a].sort();
  const sb = [...b].sort();
  return sa.every((v, i) => v === sb[i]);
}

/**
 * Chấm một câu — so khớp với đáp án đúng từ thư viện (tick xanh).
 */
export function gradeAnswer(
  question: Pick<QuizQuestion, "type" | "options" | "prompt" | "matching">,
  selectedIds: string | string[] | Record<string, string>
): GradeResult {
  if (
    isYesNoQuestion(question as QuizQuestion) &&
    typeof selectedIds === "object" &&
    !Array.isArray(selectedIds)
  ) {
    return gradeYesNoAnswer(
      question as QuizQuestion,
      selectedIds as Record<string, YesNoChoice>
    );
  }

  const matching = getMatchingData(question as QuizQuestion);
  if (matching && typeof selectedIds === "object" && !Array.isArray(selectedIds)) {
    const r = gradeMatching(matching, selectedIds);
    return {
      isCorrect: r.isCorrect,
      selectedIds: Object.entries(selectedIds).map(([d, t]) => `${d}→${t}`),
      correctIds: matching.definitions.map(
        (d) => `${d.id}→${matching.correctMap[d.id]}`
      ),
      message: r.isCorrect
        ? "Chính xác — tất cả cặp ghép đúng!"
        : `Đúng ${r.correctCount}/${r.total} cặp. Xem đáp án bên dưới.`,
    };
  }

  const selected = normalizeSelectedIds(
    selectedIds as string | string[]
  );
  const correct = getCorrectOptionIds(question as QuizQuestion).map((id) =>
    id.toUpperCase()
  );

  if (selected.length === 0) {
    return {
      isCorrect: false,
      selectedIds: selected,
      correctIds: correct,
      message: "Bạn chưa chọn đáp án.",
    };
  }

  const isCorrect = setsEqual(selected, correct);

  if (isCorrect) {
    return {
      isCorrect: true,
      selectedIds: selected,
      correctIds: correct,
      message: "Chính xác!",
    };
  }

  const type = question.type;
  if (type === "multiple") {
    return {
      isCorrect: false,
      selectedIds: selected,
      correctIds: correct,
      message: `Chưa đúng. Cần chọn đúng ${correct.length} đáp án.`,
    };
  }

  return {
    isCorrect: false,
    selectedIds: selected,
    correctIds: correct,
    message: "Sai rồi. Xem đáp án đúng bên dưới.",
  };
}

export function optionStyle(
  option: QuizOption,
  selectedIds: string[],
  revealed: boolean
): "default" | "selected" | "correct" | "wrong" | "missed" {
  const id = option.id.toUpperCase();
  const selected = selectedIds.map((s) => s.toUpperCase());
  const isSelected = selected.includes(id);

  if (!revealed) {
    return isSelected ? "selected" : "default";
  }

  if (option.isCorrect && isSelected) return "correct";
  if (option.isCorrect && !isSelected) return "missed";
  if (!option.isCorrect && isSelected) return "wrong";
  return "default";
}
