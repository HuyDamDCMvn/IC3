import type { QuizQuestion } from "@ic3-quiz/core";

/** Bố cục giống PDF IC3 Review. */
export type PdfLayoutKind =
  | "mc-text"
  | "mc-side-image"
  | "mc-image-grid"
  | "yesno"
  | "matching";

export function getPdfLayoutKind(question: QuizQuestion): PdfLayoutKind {
  const imageOpts = question.options.filter((o) => o.imageUrl).length;
  const textOpts = question.options.length - imageOpts;
  const hasSnapshot = Boolean(question.snapshotUrl);

  if (question.type === "matching" || question.matching) return "matching";
  if (
    question.type === "yesno" ||
    /chon\s*co|chon\s*dung|manh.*yeu|mật\s*khẩu.*mạnh/i.test(question.prompt)
  ) {
    return "yesno";
  }
  if (imageOpts >= 2 && imageOpts >= textOpts) return "mc-image-grid";
  if (hasSnapshot && imageOpts === 0) return "mc-side-image";
  return "mc-text";
}
