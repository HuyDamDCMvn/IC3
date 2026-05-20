import type { GradeResult, QuizOption, QuizQuestion } from "./types.js";

export type YesNoChoice = "yes" | "no";
export type YesNoLabelMode =
  | "co-khong"
  | "dung-sai"
  | "fact-opinion";

/** Một mệnh đề — isCorrect=true → chọn nhãn「yes」(Có/Đúng/Thực tế) */
export interface YesNoStatement {
  id: string;
  text: string;
  isCorrect: boolean;
}

const YESNO_CO_PROMPT_RE =
  /ch[oơ]n\s*c[oó]|c[oó]\s+n[eê]u.*d[uú]ng|kh[oô]ng\s+n[eê]u.*sai|chon\s+co\s+hoac/i;

const YESNO_DUNG_PROMPT_RE =
  /ch[oơ]n\s*[dđ][uú]ng|[dđ][uú]ng\s+n[eê]u|[dđ][uú]ng\s+ho[aă]c\s*sai|sai\s+n[eê]u.*[dđ][uú]ng|dung.*sai/i;

const YESNO_FACT_PROMPT_RE =
  /th[uự]c\s*t[eé]|thyc\s*t[eé]|ý\s*ki[eế]n|y\s*ki[eế]n/i;

const PREFIX_CO_RE = /^(c[oó]|kh[oô]ng|co|khong)\s*(.*)$/i;
const PREFIX_DUNG_RE = /^([dđ][uú]ng|sai|dung)\s*(.*)$/i;
const PREFIX_FACT_RE = /^(th[uự]c\s*t[eé]|thyc\s*t[eé]|fact)\s*(.*)$/i;
const PREFIX_OPINION_RE = /^(ý\s*ki[eế]n|y\s*ki[eế]n|opinion)\s*(.*)$/i;

const ONLY_CO_RE = /^(c[oó]|kh[oô]ng|co|khong)$/i;
const ONLY_DUNG_RE = /^[dđ][uú]ng$|^sai$|^dung$/i;
const ONLY_FACT_RE = /^(th[uự]c\s*t[eé]|thyc\s*t[eé]|fact)/i;
const ONLY_OPINION_RE = /^(ý\s*ki[eế]n|y\s*ki[eế]n|opinion)/i;

export function getYesNoLabelMode(
  prompt: string,
  stored?: YesNoLabelMode
): YesNoLabelMode {
  if (stored) return stored;
  if (
    /ch[oơ]n|hay\s+chon/i.test(prompt) &&
    /th[uự]c|thyc/i.test(prompt) &&
    /ki[eế]n|opinion/i.test(prompt)
  ) {
    return "fact-opinion";
  }
  if (YESNO_DUNG_PROMPT_RE.test(prompt)) return "dung-sai";
  return "co-khong";
}

export function getYesNoLabels(mode: YesNoLabelMode): {
  yes: string;
  no: string;
  hint: string;
} {
  switch (mode) {
    case "dung-sai":
      return {
        yes: "Đúng",
        no: "Sai",
        hint: "Chọn Đúng nếu mệnh đề đúng, Sai nếu sai.",
      };
    case "fact-opinion":
      return {
        yes: "Thực tế",
        no: "Ý kiến",
        hint: "Chọn Thực tế nếu là sự thật có thể kiểm chứng, Ý kiến nếu là quan điểm cá nhân.",
      };
    default:
      return {
        yes: "Có",
        no: "Không",
        hint: "Chọn Có nếu mệnh đề đúng, Không nếu sai.",
      };
  }
}

export function isYesNoPrompt(prompt: string): boolean {
  return (
    YESNO_CO_PROMPT_RE.test(prompt) ||
    YESNO_DUNG_PROMPT_RE.test(prompt) ||
    getYesNoLabelMode(prompt) === "fact-opinion"
  );
}

export function isYesNoQuestion(
  q: Pick<QuizQuestion, "type" | "prompt" | "yesNoMode">
): boolean {
  return (
    q.type === "yesno" ||
    (q.type === "truefalse" && isYesNoPrompt(q.prompt))
  );
}

export function getYesNoStatements(question: QuizQuestion): YesNoStatement[] {
  return question.options.map((o) => ({
    id: o.id,
    text: o.text,
    isCorrect: o.isCorrect,
  }));
}

function isOpinionLabel(text: string): boolean {
  return ONLY_OPINION_RE.test(text.trim());
}

function isFactLabel(text: string): boolean {
  return ONLY_FACT_RE.test(text.trim());
}

/** Chữ xanh trên nhãn dropdown = đáp án đúng là nhãn đang hiển thị */
export function answerIsFactFromLabel(
  labelText: string,
  visGreen: boolean | null
): boolean {
  const opinion = isOpinionLabel(labelText);
  const fact = isFactLabel(labelText);
  if (visGreen === null) {
    if (opinion) return false;
    if (fact) return true;
    return true;
  }
  if (opinion) return !visGreen;
  if (fact) return visGreen;
  return visGreen;
}

/** Parse prefix OCR theo chế độ nhãn */
export function parseYesNoLine(
  text: string,
  mode: YesNoLabelMode = "co-khong"
): { prefix: YesNoChoice | null; statement: string } {
  const t = text.trim();
  if (!t) return { prefix: null, statement: "" };

  if (mode === "fact-opinion") {
    if (ONLY_OPINION_RE.test(t)) {
      return { prefix: "no", statement: "" };
    }
    if (ONLY_FACT_RE.test(t)) {
      return { prefix: "yes", statement: "" };
    }
    const mo = PREFIX_OPINION_RE.exec(t);
    if (mo) {
      return { prefix: "no", statement: (mo[2] || "").trim() };
    }
    const mf = PREFIX_FACT_RE.exec(t);
    if (mf) {
      return { prefix: "yes", statement: (mf[2] || "").trim() };
    }
    return { prefix: null, statement: t };
  }

  if (mode === "dung-sai") {
    if (ONLY_DUNG_RE.test(t)) {
      const low = t.toLowerCase();
      return {
        prefix: low.startsWith("s") ? "no" : "yes",
        statement: "",
      };
    }
    const m = PREFIX_DUNG_RE.exec(t);
    if (!m) return { prefix: null, statement: t };
    const label = m[1].toLowerCase();
    const rest = (m[2] || "").trim();
    const prefix: YesNoChoice = label.startsWith("s") ? "no" : "yes";
    return { prefix, statement: rest };
  }

  if (ONLY_CO_RE.test(t)) {
    const low = t.toLowerCase();
    return {
      prefix: low.startsWith("c") && !low.startsWith("kh") ? "yes" : "no",
      statement: "",
    };
  }
  const m = PREFIX_CO_RE.exec(t);
  if (!m) return { prefix: null, statement: t };
  const label = m[1].toLowerCase();
  const rest = (m[2] || "").trim();
  const prefix: YesNoChoice =
    label.startsWith("c") && !label.startsWith("kh") ? "yes" : "no";
  return { prefix, statement: rest };
}

export function expectedChoiceLabel(
  isCorrect: boolean,
  mode: YesNoLabelMode = "co-khong"
): string {
  const labels = getYesNoLabels(mode);
  return isCorrect ? labels.yes : labels.no;
}

export function gradeYesNo(
  statements: YesNoStatement[],
  answers: Record<string, YesNoChoice>
): {
  isCorrect: boolean;
  correctCount: number;
  total: number;
  rowResults: Record<string, boolean>;
} {
  const rowResults: Record<string, boolean> = {};
  let correctCount = 0;
  for (const s of statements) {
    const expected: YesNoChoice = s.isCorrect ? "yes" : "no";
    const got = answers[s.id];
    const ok = got === expected;
    rowResults[s.id] = ok;
    if (ok) correctCount++;
  }
  const total = statements.length;
  return {
    isCorrect: correctCount === total && total > 0,
    correctCount,
    total,
    rowResults,
  };
}

export function gradeYesNoAnswer(
  question: QuizQuestion,
  answers: Record<string, YesNoChoice>
): GradeResult {
  const statements = getYesNoStatements(question);
  const mode = getYesNoLabelMode(question.prompt, question.yesNoMode);
  const labels = getYesNoLabels(mode);
  const r = gradeYesNo(statements, answers);
  const correctIds = statements.map((s) =>
    s.isCorrect ? `${s.id}:${labels.yes}` : `${s.id}:${labels.no}`
  );
  const selectedIds = Object.entries(answers).map(([id, v]) => {
    const lbl = v === "yes" ? labels.yes : labels.no;
    return `${id}:${lbl}`;
  });
  return {
    isCorrect: r.isCorrect,
    selectedIds,
    correctIds,
    message: r.isCorrect
      ? "Chính xác — tất cả mệnh đề đúng!"
      : `Đúng ${r.correctCount}/${r.total} mệnh đề. Xem đáp án bên dưới.`,
  };
}

export function isDropdownLabelOnly(
  text: string,
  mode: YesNoLabelMode
): boolean {
  const t = text.trim();
  if (mode === "fact-opinion") {
    return ONLY_OPINION_RE.test(t) || ONLY_FACT_RE.test(t);
  }
  if (mode === "dung-sai") {
    return ONLY_DUNG_RE.test(t);
  }
  return ONLY_CO_RE.test(t);
}
