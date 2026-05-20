import { useMemo, useState } from "react";
import {
  expectedChoiceLabel,
  getMatchingData,
  getYesNoLabelMode,
  getYesNoLabels,
  getYesNoStatements,
  gradeMatching,
  isMatchingQuestion,
  isYesNoQuestion,
  optionStyle,
} from "@ic3-quiz/core";
import type { QuizQuestion, YesNoChoice } from "@ic3-quiz/core";
import { MatchingPuzzle } from "./MatchingPuzzle";
import { YesNoQuestion } from "./YesNoQuestion";

const TOPIC_LABELS: Record<string, string> = {
  "topic-1": "Chủ đề 1",
  "topic-2": "Chủ đề 2",
  "topic-3": "Chủ đề 3",
  "topic-4": "Chủ đề 4",
  "topic-5": "Chủ đề 5",
  "topic-6": "Chủ đề 6",
  "topic-extended": "Mở rộng",
};

type Props = {
  question: QuizQuestion;
  index: number;
  revealed: boolean;
  selected: string[];
  onToggle?: (id: string) => void;
  onMatchingMap?: (map: Record<string, string>) => void;
  matchingMap?: Record<string, string>;
  yesNoAnswers?: Record<string, YesNoChoice>;
  onYesNoChange?: (answers: Record<string, YesNoChoice>) => void;
  showMeta?: boolean;
};

export function QuestionCard({
  question,
  index,
  revealed,
  selected,
  onToggle,
  onMatchingMap,
  matchingMap = {},
  yesNoAnswers = {},
  onYesNoChange,
  showMeta = true,
}: Props) {
  const matchingData = useMemo(() => getMatchingData(question), [question]);
  const isMatching = isMatchingQuestion(question) && matchingData;
  const isYesNo = isYesNoQuestion(question);

  const [localMap, setLocalMap] = useState<Record<string, string>>({});
  const map = onMatchingMap ? matchingMap : localMap;
  const setMap = onMatchingMap ?? setLocalMap;

  const matchGrade = matchingData
    ? gradeMatching(matchingData, map)
    : null;
  const rowResults = matchGrade?.rowResults ?? {};

  if (isYesNo) {
    const statements = getYesNoStatements(question);
    const ynLabels = getYesNoLabels(
      getYesNoLabelMode(question.prompt, question.yesNoMode)
    );
    return (
      <article className="ic3-question review-card yesno-card">
        {showMeta && (
          <div className="review-card-meta">
            <span className="review-badge">
              {TOPIC_LABELS[question.topic] ?? question.topic}
              <span className="match-badge">
                {" "}
                · {ynLabels.yes} / {ynLabels.no}
              </span>
            </span>
            <span className="review-num">
              #{index + 1}
              {question.indexInTest != null &&
                ` · Q${question.indexInTest}/${question.totalInTest ?? "?"}`}
            </span>
          </div>
        )}
        <div className="ic3-question-bar">
          {question.indexInTest != null && (
            <span className="q-num">
              Question {question.indexInTest} of {question.totalInTest ?? "?"}
            </span>
          )}
          {question.prompt}
        </div>
        <div className="ic3-content">
          {question.snapshotUrl && (
            <img
              className="snapshot"
              src={question.snapshotUrl}
              alt="Câu hỏi"
            />
          )}
          <YesNoQuestion
            question={question}
            revealed={revealed}
            answers={yesNoAnswers}
            onChange={onYesNoChange ?? (() => {})}
          />
          {revealed && (
            <div className="review-answer-key">
              {statements.map((s) => (
                <div key={s.id}>
                  <strong>{s.id}.</strong>{" "}
                  {expectedChoiceLabel(
                    s.isCorrect,
                    getYesNoLabelMode(question.prompt, question.yesNoMode)
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </article>
    );
  }

  if (isMatching && matchingData) {
    return (
      <article className="ic3-question review-card matching-card">
        {showMeta && (
          <div className="review-card-meta">
            <span className="review-badge">
              {TOPIC_LABELS[question.topic] ?? question.topic}
              <span className="match-badge"> · Ghép mảnh</span>
            </span>
            <span className="review-num">
              #{index + 1}
              {question.indexInTest != null &&
                ` · Q${question.indexInTest}/${question.totalInTest ?? "?"}`}
            </span>
          </div>
        )}
        {question.snapshotUrl && (
          <img
            className="snapshot snapshot-compact"
            src={question.snapshotUrl}
            alt="Tham khảo PDF"
          />
        )}
        <MatchingPuzzle
          data={matchingData}
          revealed={revealed}
          rowResults={rowResults}
          userMap={map}
          onMapChange={setMap}
        />
        {revealed && matchGrade && (
          <div
            className={`feedback ${matchGrade.isCorrect ? "ok" : "err"}`}
            style={{ margin: "0 1rem 1rem" }}
          >
            {matchGrade.isCorrect
              ? "✓ Tất cả cặp ghép đúng!"
              : `✗ Đúng ${matchGrade.correctCount}/${matchGrade.total} cặp`}
          </div>
        )}
      </article>
    );
  }

  const readOnly = !onToggle;

  return (
    <article className="ic3-question review-card">
      {showMeta && (
        <div className="review-card-meta">
          <span className="review-badge">
            {TOPIC_LABELS[question.topic] ?? question.topic}
            {question.testId ? ` · ${question.testId.replace("test-", "Test ")}` : ""}
          </span>
          <span className="review-num">
            #{index + 1}
            {question.indexInTest != null &&
              ` · Q${question.indexInTest}/${question.totalInTest ?? "?"}`}
          </span>
        </div>
      )}
      <div className="ic3-question-bar">
        {question.indexInTest != null && (
          <span className="q-num">
            Question {question.indexInTest} of {question.totalInTest ?? "?"}
          </span>
        )}
        {question.prompt}
      </div>
      <div className="ic3-content">
        {question.snapshotUrl && (
          <img className="snapshot" src={question.snapshotUrl} alt="Câu hỏi" />
        )}
        <div className="options-grid">
          {question.options.map((opt) => {
            const style = readOnly
              ? revealed && opt.isCorrect
                ? "correct"
                : "default"
              : optionStyle(opt, selected, revealed);
            return (
              <button
                key={opt.id}
                type="button"
                className={`option ${style}`}
                onClick={() => onToggle?.(opt.id)}
                disabled={readOnly || revealed}
              >
                <span className="option-radio" aria-hidden />
                <div className="option-body">
                  {opt.imageUrl && (
                    <img
                      className="option-image"
                      src={opt.imageUrl}
                      alt={opt.text}
                    />
                  )}
                  <span>
                    <strong>{opt.id}.</strong> {opt.text}
                  </span>
                </div>
                {revealed && opt.isCorrect && (
                  <span className="option-tag">✓ Đúng</span>
                )}
                {!readOnly && revealed && style === "wrong" && (
                  <span className="option-tag">✗ Sai</span>
                )}
              </button>
            );
          })}
        </div>
        {revealed && (
          <div className="review-answer-key">
            Đáp án đúng:{" "}
            <strong>
              {question.options
                .filter((o) => o.isCorrect)
                .map((o) => o.id)
                .join(", ") || "—"}
            </strong>
          </div>
        )}
      </div>
    </article>
  );
}
