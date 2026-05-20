import { gradeAnswer, getCorrectOptionIds } from "./answerKey.js";
import { isYesNoQuestion } from "./yesno.js";
import type {
  QuestionBank,
  QuizQuestion,
  QuizSessionResult,
} from "./types.js";

export interface QuizFilter {
  topic?: string;
  testId?: string;
  limit?: number;
  shuffle?: boolean;
}

function normalizeOption(raw: Record<string, unknown>) {
  return {
    id: String(raw.id ?? ""),
    text: String(raw.text ?? ""),
    isCorrect: Boolean(raw.isCorrect ?? raw.is_correct),
    imageUrl: raw.imageUrl
      ? String(raw.imageUrl)
      : raw.image_url
        ? String(raw.image_url)
        : undefined,
  };
}

function normalizeQuestion(raw: Record<string, unknown>): QuizQuestion {
  const opts = Array.isArray(raw.options) ? raw.options : [];
  return {
    id: String(raw.id),
    topic: String(raw.topic),
    testId: String(raw.testId ?? raw.test_id ?? ""),
    prompt: String(raw.prompt),
    type: (raw.type as QuizQuestion["type"]) || "single",
    options: opts.map((o) =>
      normalizeOption(o as Record<string, unknown>)
    ),
    page: raw.page as number | undefined,
    indexInTest: (raw.indexInTest ?? raw.index_in_test) as number | undefined,
    snapshotUrl: raw.snapshotUrl
      ? String(raw.snapshotUrl)
      : raw.snapshot_url
        ? String(raw.snapshot_url)
        : undefined,
    images: Array.isArray(raw.images)
      ? (raw.images as string[])
      : undefined,
    matching: raw.matching as QuizQuestion["matching"],
    yesNoMode: (raw.yesNoMode ?? raw.yes_no_mode) as
      | QuizQuestion["yesNoMode"]
      | undefined,
  };
}

export function loadQuestionBank(data: QuestionBank): QuizQuestion[] {
  return data.questions
    .map((q) =>
      normalizeQuestion(q as unknown as Record<string, unknown>)
    )
    .filter(
      (q) =>
        q.prompt &&
        (q.type === "matching" ||
          q.matching ||
          isYesNoQuestion(q) ||
          q.options.some((o) => o.isCorrect))
    );
}

/** Câu đủ điều kiện làm bài (có đáp án hoặc loại đặc biệt). */
export function getPlayableQuestions(questions: QuizQuestion[]): QuizQuestion[] {
  return questions.filter(
    (q) =>
      q.prompt?.trim() &&
      (q.type === "matching" ||
        q.matching ||
        isYesNoQuestion(q) ||
        q.options.length >= 1)
  );
}

export interface MixedExamOptions {
  /** Trộn đều theo chủ đề (mặc định true) */
  balanceTopics?: boolean;
  shuffle?: boolean;
}

/**
 * Tạo đề thi trộn: lấy `count` câu từ toàn ngân hàng, ưu tiên mỗi chủ đề có mặt.
 */
export function buildMixedExam(
  questions: QuizQuestion[],
  count: number,
  options: MixedExamOptions = {}
): QuizQuestion[] {
  const { balanceTopics = true, shuffle: doShuffle = true } = options;
  const pool = getPlayableQuestions(questions);
  if (pool.length === 0) return [];
  const n = Math.min(count, pool.length);

  if (!balanceTopics) {
    const list = doShuffle ? shuffle(pool) : [...pool];
    return list.slice(0, n);
  }

  const byTopic = new Map<string, QuizQuestion[]>();
  for (const q of pool) {
    const list = byTopic.get(q.topic) ?? [];
    list.push(q);
    byTopic.set(q.topic, list);
  }

  const topics = [...byTopic.keys()].sort();
  const basePerTopic = Math.max(1, Math.floor(n / topics.length));
  const picked: QuizQuestion[] = [];
  const used = new Set<string>();

  for (const topic of topics) {
    const bucket = doShuffle ? shuffle(byTopic.get(topic)!) : [...byTopic.get(topic)!];
    for (const q of bucket.slice(0, basePerTopic)) {
      if (picked.length >= n) break;
      picked.push(q);
      used.add(q.id);
    }
  }

  const remainder = doShuffle
    ? shuffle(pool.filter((q) => !used.has(q.id)))
    : pool.filter((q) => !used.has(q.id));
  for (const q of remainder) {
    if (picked.length >= n) break;
    picked.push(q);
    used.add(q.id);
  }

  return doShuffle ? shuffle(picked) : picked;
}

export function filterQuestions(
  questions: QuizQuestion[],
  filter: QuizFilter = {}
): QuizQuestion[] {
  let list = [...questions];
  if (filter.topic) {
    list = list.filter((q) => q.topic === filter.topic);
  }
  if (filter.testId) {
    list = list.filter((q) => q.testId === filter.testId);
  }
  if (filter.shuffle) {
    list = shuffle(list);
  }
  if (filter.limit && filter.limit > 0) {
    list = list.slice(0, filter.limit);
  }
  return list;
}

export function getTopics(questions: QuizQuestion[]): string[] {
  return [...new Set(questions.map((q) => q.topic))].sort();
}

export function getTestsForTopic(
  questions: QuizQuestion[],
  topic: string
): string[] {
  return [
    ...new Set(questions.filter((q) => q.topic === topic).map((q) => q.testId)),
  ].sort();
}

export interface AnswerSubmission {
  questionId: string;
  selectedIds: string[] | Record<string, string>;
}

export function gradeSession(
  questions: QuizQuestion[],
  submissions: AnswerSubmission[]
): QuizSessionResult {
  const byId = new Map(questions.map((q) => [q.id, q]));
  const details: QuizSessionResult["details"] = [];
  let correct = 0;

  for (const sub of submissions) {
    const q = byId.get(sub.questionId);
    if (!q) continue;
    const grade = gradeAnswer(q, sub.selectedIds);
    if (grade.isCorrect) correct++;
    details.push({
      questionId: q.id,
      prompt: q.prompt,
      isCorrect: grade.isCorrect,
      selectedIds: grade.selectedIds,
      correctIds:
        grade.correctIds.length > 0 ? grade.correctIds : getCorrectOptionIds(q),
    });
  }

  const total = details.length;
  const wrong = total - correct;
  return {
    total,
    correct,
    wrong,
    scorePercent: total ? Math.round((correct / total) * 100) : 0,
    details,
  };
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
