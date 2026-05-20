import type { MatchItem, MatchingData, QuizQuestion } from "./types.js";

export type { MatchItem, MatchingData };

const MATCH_HINT =
  /gh[eé]p|n[oố]i\s+m[oỗ]i|kéo.*sang|di chuy[eể]n.*sang|match each/i;

export function isMatchingQuestion(q: QuizQuestion): boolean {
  if (q.type === "matching" && q.matching) return true;
  return MATCH_HINT.test(q.prompt) || Boolean(q.matching);
}

/** Parse term options like "4 (Font) Phông chữ" or "3. Trình chiếu" */
function parseTermOption(text: string): MatchItem | null {
  const t = text.trim();
  let m = t.match(/^(\d+)\s*[\.\)]\s*(.+)$/i);
  if (m) return { id: m[1], text: m[2].trim() };
  m = t.match(/^(\d+)\s*\(([^)]+)\)\s*(.*)$/i);
  if (m) {
    const label = m[3].trim() || m[2].trim();
    return { id: m[1], text: `${label} (${m[2].trim()})`.trim() };
  }
  m = t.match(/^(.+?)\s+(\d+)\.\s*\(([^)]+)\)/i);
  if (m) return { id: m[2], text: `${m[1].trim()} (${m[3]})` };
  return null;
}

function splitDefinitionsFromPrompt(prompt: string): string[] {
  let body = prompt
    .replace(MATCH_HINT, "")
    .replace(/để trả lời[^.]*\./gi, "")
    .replace(/hãy kéo[^.]*\./gi, "")
    .trim();

  const numbered = body.split(/(?=\d+\.\s)/).filter((s) => /^\d+\./.test(s.trim()));
  if (numbered.length >= 2) {
    return numbered.map((s) => s.replace(/^\d+\.\s*/, "").trim());
  }

  const sentences = body
    .split(/\.\s+(?=[A-ZÀ-ỹM\d]|Mot |Một |Màt |Hay |Gui )/i)
    .map((s) => s.replace(/\.$/, "").trim())
    .filter((s) => s.length > 25 && !MATCH_HINT.test(s));

  return sentences.slice(0, 6);
}

export function tryParseMatching(q: QuizQuestion): MatchingData | null {
  if (q.matching) return q.matching;

  const instruction =
    q.options.find((o) => MATCH_HINT.test(o.text))?.text ||
    (MATCH_HINT.test(q.prompt.split(".")[0])
      ? q.prompt.split(".")[0] + "."
      : "Ghép mỗi thuật ngữ với định nghĩa tương ứng.");

  const terms: MatchItem[] = [];
  for (const o of q.options) {
    const term = parseTermOption(o.text);
    if (term && !terms.some((t) => t.id === term.id)) terms.push(term);
  }

  const defTexts = splitDefinitionsFromPrompt(q.prompt);
  if (terms.length < 2 || defTexts.length < 2) return null;

  const n = Math.min(terms.length, defTexts.length);
  const definitions: MatchItem[] = defTexts.slice(0, n).map((text, i) => ({
    id: String(i + 1),
    text,
  }));

  const correctMap: Record<string, string> = {};
  definitions.forEach((d, i) => {
    if (terms[i]) correctMap[d.id] = terms[i].id;
  });

  if (Object.keys(correctMap).length < 2) return null;

  return {
    instruction,
    definitions,
    terms: terms.slice(0, Math.max(n, terms.length)),
    correctMap,
  };
}

export function getMatchingData(q: QuizQuestion): MatchingData | null {
  return q.matching ?? tryParseMatching(q);
}

export function gradeMatching(
  data: MatchingData,
  userMap: Record<string, string>
): {
  isCorrect: boolean;
  correctCount: number;
  total: number;
  rowResults: Record<string, boolean>;
} {
  const total = data.definitions.length;
  const rowResults: Record<string, boolean> = {};
  let correctCount = 0;

  for (const def of data.definitions) {
    const expected = data.correctMap[def.id];
    const got = userMap[def.id];
    const ok = expected != null && got === expected;
    rowResults[def.id] = ok;
    if (ok) correctCount++;
  }

  return {
    isCorrect: correctCount === total && total > 0,
    correctCount,
    total,
    rowResults,
  };
}
