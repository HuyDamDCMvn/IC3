import {
  expectedChoiceLabel,
  getYesNoLabelMode,
  getYesNoLabels,
  getYesNoStatements,
  gradeYesNo,
  type YesNoChoice,
} from "@ic3-quiz/core";
import type { QuizQuestion } from "@ic3-quiz/core";

type Props = {
  question: QuizQuestion;
  revealed: boolean;
  answers: Record<string, YesNoChoice>;
  onChange: (answers: Record<string, YesNoChoice>) => void;
};

export function YesNoQuestion({
  question,
  revealed,
  answers,
  onChange,
}: Props) {
  const mode = getYesNoLabelMode(question.prompt, question.yesNoMode);
  const labels = getYesNoLabels(mode);
  const statements = getYesNoStatements(question);
  const grade = gradeYesNo(statements, answers);

  const setChoice = (id: string, value: YesNoChoice) => {
    if (revealed) return;
    onChange({ ...answers, [id]: value });
  };

  return (
    <div className="yesno-question">
      <p className="yesno-hint">{labels.hint}</p>
      <ul className="yesno-rows">
        {statements.map((s) => {
          const choice = answers[s.id];
          const rowOk = grade.rowResults[s.id];
          const rowClass =
            revealed && choice !== undefined
              ? rowOk
                ? "yesno-row ok"
                : "yesno-row err"
              : "yesno-row";

          return (
            <li key={s.id} className={rowClass}>
              <select
                className="yesno-select"
                value={choice ?? ""}
                disabled={revealed}
                aria-label={`Lựa chọn cho mệnh đề ${s.id}`}
                onChange={(e) =>
                  setChoice(s.id, e.target.value as YesNoChoice)
                }
              >
                <option value="" disabled>
                  —
                </option>
                <option value="yes">{labels.yes}</option>
                <option value="no">{labels.no}</option>
              </select>
              <span className="yesno-statement">{s.text}</span>
              {revealed && (
                <span className="yesno-expected">
                  → {expectedChoiceLabel(s.isCorrect, mode)}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {revealed && (
        <div className={`feedback ${grade.isCorrect ? "ok" : "err"}`}>
          {grade.isCorrect
            ? "✓ Tất cả mệnh đề đúng!"
            : `✗ Đúng ${grade.correctCount}/${grade.total} mệnh đề`}
        </div>
      )}
    </div>
  );
}
