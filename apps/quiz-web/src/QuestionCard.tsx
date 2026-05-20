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
import { getPdfLayoutKind } from "./pdfLayout";
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

function ResourcesLine({ question }: { question: QuizQuestion }) {
  if (question.indexInTest == null) return null;
  return (
    <div className="ic3-resources-line">
      Resources | Question {question.indexInTest} of{" "}
      {question.totalInTest ?? "?"}
    </div>
  );
}

function QuestionBar({ prompt }: { prompt: string }) {
  return <div className="ic3-question-bar">{prompt}</div>;
}

function PdfOptionRow({
  opt,
  style,
  revealed,
  readOnly,
  showLetter,
  onToggle,
}: {
  opt: QuizQuestion["options"][0];
  style: string;
  revealed: boolean;
  readOnly: boolean;
  showLetter: boolean;
  onToggle?: (id: string) => void;
}) {
  return (
    <button
      type="button"
      className={`option pdf-option ${style}`}
      onClick={() => onToggle?.(opt.id)}
      disabled={readOnly || revealed}
    >
      <span className="option-mark" aria-hidden>
        {revealed && opt.isCorrect && (
          <span className="pdf-answer-check" title="Đáp án đúng">
            ✓
          </span>
        )}
        {revealed && style === "wrong" && (
          <span className="pdf-answer-wrong" title="Đã chọn sai">
            ●
          </span>
        )}
      </span>
      <span className="option-radio" aria-hidden />
      <div className="option-body">
        {opt.imageUrl && (
          <img className="option-image" src={opt.imageUrl} alt={opt.text} />
        )}
        <span className="option-text">
          {showLetter && !opt.imageUrl ? (
            <>
              <strong>{opt.id}.</strong> {opt.text}
            </>
          ) : (
            opt.text
          )}
        </span>
      </div>
    </button>
  );
}

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
  const pdfMode = !showMeta;
  const layoutKind = getPdfLayoutKind(question);
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

  const rootClass = [
    "ic3-question",
    showMeta ? "review-card" : "pdf-page-block",
    isYesNo ? "yesno-card" : "",
    isMatching ? "matching-card" : "",
    layoutKind === "mc-side-image" ? "has-side-figure" : "",
    layoutKind === "mc-image-grid" ? "has-image-grid" : "",
  ]
    .filter(Boolean)
    .join(" ");

  if (isYesNo) {
    const statements = getYesNoStatements(question);
    const ynLabels = getYesNoLabels(
      getYesNoLabelMode(question.prompt, question.yesNoMode)
    );
    return (
      <article className={rootClass}>
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
        {pdfMode && <ResourcesLine question={question} />}
        <QuestionBar prompt={question.prompt} />
        <div className="ic3-answers-pane">
          {question.snapshotUrl && (
            <img
              className="snapshot snapshot-above"
              src={question.snapshotUrl}
              alt="Minh họa"
            />
          )}
          <YesNoQuestion
            question={question}
            revealed={revealed}
            answers={yesNoAnswers}
            onChange={onYesNoChange ?? (() => {})}
            pdfMode={pdfMode}
          />
          {revealed && (
            <div className="review-answer-key">
              {statements.map((s) => (
                <div key={s.id}>
                  <strong>{s.text}</strong> →{" "}
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
    const prompt =
      matchingData.instruction || question.prompt || "Ghép mảnh";
    return (
      <article className={rootClass}>
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
        {pdfMode && <ResourcesLine question={question} />}
        <QuestionBar prompt={prompt} />
        <div className="ic3-answers-pane">
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
            >
              {matchGrade.isCorrect
                ? "✓ Tất cả cặp ghép đúng!"
                : `✗ Đúng ${matchGrade.correctCount}/${matchGrade.total} cặp`}
            </div>
          )}
        </div>
      </article>
    );
  }

  const readOnly = !onToggle;
  const showLetter = !pdfMode;
  const optionsList = (
    <div
      className={
        layoutKind === "mc-image-grid"
          ? "options-grid options-image-grid"
          : "options-grid"
      }
    >
      {question.options.map((opt) => {
        const style = readOnly
          ? revealed && opt.isCorrect
            ? "correct"
            : "default"
          : optionStyle(opt, selected, revealed);
        return (
          <PdfOptionRow
            key={opt.id}
            opt={opt}
            style={style}
            revealed={revealed}
            readOnly={readOnly}
            showLetter={showLetter}
            onToggle={onToggle}
          />
        );
      })}
    </div>
  );

  const figure =
    question.snapshotUrl && layoutKind === "mc-side-image" ? (
      <div className="ic3-figure-column">
        <img
          className="snapshot"
          src={question.snapshotUrl}
          alt="Minh họa câu hỏi"
        />
      </div>
    ) : null;

  const snapshotAbove =
    question.snapshotUrl && layoutKind !== "mc-side-image" ? (
      <img className="snapshot" src={question.snapshotUrl} alt="Minh họa câu hỏi" />
    ) : null;

  return (
    <article className={rootClass}>
      {showMeta && (
        <div className="review-card-meta">
          <span className="review-badge">
            {TOPIC_LABELS[question.topic] ?? question.topic}
            {question.testId
              ? ` · ${question.testId.replace("test-", "Test ")}`
              : ""}
          </span>
          <span className="review-num">
            #{index + 1}
            {question.indexInTest != null &&
              ` · Q${question.indexInTest}/${question.totalInTest ?? "?"}`}
          </span>
        </div>
      )}
      {pdfMode && <ResourcesLine question={question} />}
      <QuestionBar prompt={question.prompt} />
      <div className="ic3-answers-pane">
        {pdfMode && question.type === "multiple" && (
          <p className="mc-hint-pdf">Chọn tất cả đáp án đúng (nhiều lựa chọn).</p>
        )}
        {snapshotAbove}
        <div className="ic3-body-row">
          <div className="ic3-options-column">{optionsList}</div>
          {figure}
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
