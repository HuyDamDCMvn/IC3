import { useCallback, useEffect, useMemo, useState } from "react";

import {
  buildMixedExam,
  filterQuestions,
  getMatchingData,
  getTestsForTopic,
  getTopics,
  getYesNoStatements,
  gradeAnswer,
  gradeSession,
  isMatchingQuestion,
  isYesNoQuestion,
  loadQuestionBank,
  type AnswerSubmission,
  type QuestionBank,
  type QuizQuestion,
  type YesNoChoice,
} from "@ic3-quiz/core";

import { QuestionCard } from "./QuestionCard";

import { InspectTab } from "./InspectTab";



type AppTab = "quiz" | "inspect";

type Phase = "setup" | "quiz" | "results";



const TOPIC_LABELS: Record<string, string> = {

  "topic-1": "Chủ đề 1 — Phần cứng & thiết bị",

  "topic-2": "Chủ đề 2 — Công dân số",

  "topic-3": "Chủ đề 3 — Internet & tìm kiếm",

  "topic-4": "Chủ đề 4 — Ứng dụng văn phòng",

  "topic-5": "Chủ đề 5 — Giao tiếp số",

  "topic-6": "Chủ đề 6 — An toàn & thiết bị",

  "topic-extended": "Chủ đề mở rộng",

};

const PRACTICE_EXAM_SIZE = 45;



function questionKey(q: QuizQuestion): string {
  return `${q.topic}|${q.testId}|${q.indexInTest ?? ""}`;
}

async function loadAllBanks(): Promise<QuizQuestion[]> {
  const merged = new Map<string, QuizQuestion>();

  const urls = [
    "/questions.json",
    "/questions-merged.json",
    "/quiz-visual/questions.json",
  ];

  for (const url of urls) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const data: QuestionBank = await res.json();
      const preferVisual = url.includes("quiz-visual");
      for (const q of loadQuestionBank(data)) {
        const key = questionKey(q);
        if (!merged.has(key) || preferVisual) {
          merged.set(key, q);
        }
      }
    } catch {
      /* skip */
    }
  }

  return [...merged.values()];
}



export default function App() {

  const [bank, setBank] = useState<QuizQuestion[]>([]);

  const [loading, setLoading] = useState(true);

  const [appTab, setAppTab] = useState<AppTab>("quiz");

  const [phase, setPhase] = useState<Phase>("setup");

  const [topic, setTopic] = useState("");

  const [testId, setTestId] = useState("");

  const [limit, setLimit] = useState(10);

  const [visualOnly, setVisualOnly] = useState(false);

  const [questions, setQuestions] = useState<QuizQuestion[]>([]);

  const [index, setIndex] = useState(0);

  const [selected, setSelected] = useState<string[]>([]);

  const [revealed, setRevealed] = useState(false);

  const [submissions, setSubmissions] = useState<AnswerSubmission[]>([]);
  const [matchingMap, setMatchingMap] = useState<Record<string, string>>({});
  const [yesNoAnswers, setYesNoAnswers] = useState<Record<string, YesNoChoice>>(
    {}
  );
  const [examMode, setExamMode] = useState<"custom" | "mixed45">("custom");



  useEffect(() => {

    loadAllBanks()

      .then((loaded) => {

        setBank(loaded);

        const topics = getTopics(loaded);

        if (topics[0]) {

          setTopic(topics[0]);

          setTestId(getTestsForTopic(loaded, topics[0])[0] ?? "");

        }

      })

      .finally(() => setLoading(false));

  }, []);



  const filteredBank = useMemo(

    () =>

      visualOnly

        ? bank.filter((q) => q.snapshotUrl || q.options.some((o) => o.imageUrl))

        : bank,

    [bank, visualOnly]

  );



  const tests = useMemo(

    () => (topic ? getTestsForTopic(filteredBank, topic) : []),

    [filteredBank, topic]

  );



  const resetQuizState = useCallback(() => {
    setIndex(0);
    setSelected([]);
    setRevealed(false);
    setSubmissions([]);
    setMatchingMap({});
    setYesNoAnswers({});
  }, []);

  const startQuiz = useCallback(() => {
    const qs = filterQuestions(filteredBank, {
      topic: topic || undefined,
      testId: testId || undefined,
      limit,
      shuffle: true,
    });
    setExamMode("custom");
    setQuestions(qs);
    resetQuizState();
    setPhase("quiz");
    setAppTab("quiz");
  }, [filteredBank, topic, testId, limit, resetQuizState]);

  const startMixedExam = useCallback(() => {
    const qs = buildMixedExam(filteredBank, PRACTICE_EXAM_SIZE, {
      balanceTopics: true,
      shuffle: true,
    });
    setExamMode("mixed45");
    setQuestions(qs);
    resetQuizState();
    setPhase("quiz");
    setAppTab("quiz");
  }, [filteredBank, resetQuizState]);



  const current = questions[index];

  const isMultiple = current?.type === "multiple";



  const toggleOption = (id: string) => {

    if (revealed) return;

    const up = id.toUpperCase();

    if (isMultiple) {

      setSelected((prev) =>

        prev.includes(up) ? prev.filter((x) => x !== up) : [...prev, up]

      );

    } else {

      setSelected([up]);

    }

  };



  const checkAnswer = () => {
    if (!current) return;
    const isMatch = isMatchingQuestion(current);
    const isYesNo = isYesNoQuestion(current);
    if (isMatch) {
      const need = getMatchingData(current)?.definitions.length ?? 1;
      if (Object.keys(matchingMap).length < need) return;
    } else if (isYesNo) {
      const need = getYesNoStatements(current).length;
      if (Object.keys(yesNoAnswers).length < need) return;
    } else if (selected.length === 0) return;

    setRevealed(true);
    setSubmissions((prev) => [
      ...prev.filter((s) => s.questionId !== current.id),
      {
        questionId: current.id,
        selectedIds: isMatch
          ? matchingMap
          : isYesNo
            ? yesNoAnswers
            : selected,
      },
    ]);
  };



  const nextQuestion = () => {

    if (index + 1 < questions.length) {

      setIndex((i) => i + 1);

      setSelected([]);
      setMatchingMap({});
      setYesNoAnswers({});
      setRevealed(false);

    } else {

      setPhase("results");

    }

  };

  const canCheck = current
    ? isMatchingQuestion(current)
      ? Object.keys(matchingMap).length >=
        (getMatchingData(current)?.definitions.length ?? 99)
      : isYesNoQuestion(current)
        ? Object.keys(yesNoAnswers).length >=
          getYesNoStatements(current).length
        : selected.length > 0
    : false;

  const grade = current
    ? gradeAnswer(
        current,
        isMatchingQuestion(current)
          ? matchingMap
          : isYesNoQuestion(current)
            ? yesNoAnswers
            : selected
      )
    : null;



  const sessionResult = useMemo(

    () => gradeSession(questions, submissions),

    [questions, submissions, phase]

  );



  if (loading) {

    return (

      <div className="app">

        <div className="pdf-banner">

          <span className="brand">TTNNTH AN QUỐC VIỆT</span>

          TÀI LIỆU ÔN THI · IC3 GS6 SPARK LEVEL 1

        </div>

        <p className="loading">Đang tải câu hỏi (MinerU + PDF)…</p>

      </div>

    );

  }



  return (

    <div className="app">

      <div className="pdf-banner">

        <span className="brand">TTNNTH AN QUỐC VIỆT</span>

        * TÀI LIỆU ÔN THI * IC3 GS6 SPARK LEVEL 1

      </div>



      <div className="app-title">

        <h1>Luyện trắc nghiệm IC3 Spark LV1</h1>

        <p>Giao diện giống IC3 Review · {bank.length} câu trong ngân hàng</p>

      </div>



      <nav className="app-tabs" role="tablist">

        <button

          type="button"

          role="tab"

          aria-selected={appTab === "quiz"}

          className={`app-tab ${appTab === "quiz" ? "active" : ""}`}

          onClick={() => {

            setAppTab("quiz");

            if (phase === "quiz" || phase === "results") return;

            setPhase("setup");

          }}

        >

          Làm bài thi

        </button>

        <button

          type="button"

          role="tab"

          aria-selected={appTab === "inspect"}

          className={`app-tab ${appTab === "inspect" ? "active" : ""}`}

          onClick={() => setAppTab("inspect")}

        >

          Kiểm tra câu hỏi ({bank.length})

        </button>

      </nav>



      {appTab === "inspect" && <InspectTab bank={bank} />}



      {appTab === "quiz" && phase === "setup" && (

        <section className="setup card">

          <div className="practice-exam-hero">
            <h2>Thi thử {PRACTICE_EXAM_SIZE} câu</h2>
            <p>
              Trộn ngẫu nhiên {PRACTICE_EXAM_SIZE} câu từ toàn bộ ngân hàng ({filteredBank.length}{" "}
              câu), đều các chủ đề — giống đề ôn IC3.
            </p>
            <button
              type="button"
              className="btn btn-primary btn-practice"
              onClick={startMixedExam}
              disabled={filteredBank.length < PRACTICE_EXAM_SIZE}
            >
              Bắt đầu thi thử {PRACTICE_EXAM_SIZE} câu
            </button>
          </div>

          <hr className="setup-divider" />

          <h3 className="setup-subtitle">Luyện theo chủ đề / bài test</h3>

          <label>

            <input

              type="checkbox"

              checked={visualOnly}

              onChange={(e) => setVisualOnly(e.target.checked)}

            />{" "}

            Chỉ câu có hình ảnh (MinerU)

          </label>



          <label>Chủ đề</label>

          <select

            value={topic}

            onChange={(e) => {

              setTopic(e.target.value);

              setTestId(getTestsForTopic(filteredBank, e.target.value)[0] ?? "");

            }}

          >

            <option value="">Tất cả chủ đề</option>

            {getTopics(filteredBank).map((t) => (

              <option key={t} value={t}>

                {TOPIC_LABELS[t] ?? t}

              </option>

            ))}

          </select>



          <label>Bài test</label>

          <select

            value={testId}

            onChange={(e) => setTestId(e.target.value)}

            disabled={!topic}

          >

            <option value="">Tất cả bài</option>

            {tests.map((t) => (

              <option key={t} value={t}>

                {t.replace("test-", "Test ")}

              </option>

            ))}

          </select>



          <label>Số câu</label>

          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>

            {[5, 10, 15, 20, 45, 50, 100].map((n) => (

              <option key={n} value={n}>

                {n} câu

              </option>

            ))}

          </select>



          <p style={{ color: "var(--pdf-muted)", fontSize: "0.85rem" }}>

            Ngân hàng: {filteredBank.length} câu

          </p>



          <button

            type="button"

            className="btn btn-primary"

            onClick={startQuiz}

            disabled={filteredBank.length === 0}

          >

            Bắt đầu làm bài

          </button>

        </section>

      )}



      {appTab === "quiz" && phase === "quiz" && current && (

        <section className="quiz-body">

          <div className="quiz-meta">

            <span>

              {examMode === "mixed45"
                ? `Đề thi thử · Câu ${index + 1}/${questions.length}`
                : `Câu ${index + 1} / ${questions.length}`}

            </span>

            <span>{TOPIC_LABELS[current.topic] ?? current.topic}</span>

          </div>

          <div className="progress-bar">

            <div

              className="progress-bar-fill"

              style={{ width: `${((index + 1) / questions.length) * 100}%` }}

            />

          </div>



          <QuestionCard

            question={current}

            index={index}

            revealed={revealed}

            selected={selected}
            matchingMap={matchingMap}
            onMatchingMap={setMatchingMap}
            yesNoAnswers={yesNoAnswers}
            onYesNoChange={setYesNoAnswers}
            onToggle={toggleOption}
            showMeta={false}
          />



          {revealed && grade && (

            <div

              className={`feedback ${grade.isCorrect ? "ok" : "err"}`}

              style={{ margin: "0 1rem 1rem" }}

            >

              {grade.isCorrect ? "✓ Chính xác!" : "✗ Chưa đúng"}

              {!grade.isCorrect && (

                <div className="correct-list">

                  Đáp án đúng:{" "}

                  {current.options

                    .filter((o) => o.isCorrect)

                    .map((o) => o.id)

                    .join(", ")}

                </div>

              )}

            </div>

          )}



          <div className="actions" style={{ margin: "0 1rem 1rem" }}>

            {!revealed ? (

              <button

                type="button"

                className="btn btn-primary"

                disabled={!canCheck}
                onClick={checkAnswer}

              >

                Kiểm tra đáp án

              </button>

            ) : (

              <button

                type="button"

                className="btn btn-primary"

                onClick={nextQuestion}

              >

                {index + 1 < questions.length

                  ? "Câu tiếp theo →"

                  : "Xem kết quả"}

              </button>

            )}

          </div>

        </section>

      )}



      {appTab === "quiz" && phase === "results" && (

        <section className="quiz-body">

          <div className="card score-ring">

            {examMode === "mixed45" && (
              <p className="score-exam-label">Kết quả đề thi thử {PRACTICE_EXAM_SIZE} câu</p>
            )}

            <div className="percent">{sessionResult.scorePercent}%</div>

            <div style={{ color: "var(--pdf-muted)" }}>

              Đúng {sessionResult.correct} / {sessionResult.total} — Sai{" "}

              {sessionResult.wrong}

            </div>

          </div>



          <div className="card result-list">

            <h3 style={{ marginTop: 0, color: "var(--accent)" }}>Chi tiết</h3>

            {sessionResult.details.map((d, i) => (

              <div

                key={d.questionId}

                className={`result-item ${d.isCorrect ? "ok" : "err"}`}

              >

                <span className="status">

                  {d.isCorrect ? "✓ Đúng" : "✗ Sai"}

                </span>{" "}

                Câu {i + 1}: {d.prompt.slice(0, 80)}…

              </div>

            ))}

          </div>



          <div className="actions">

            <button

              type="button"

              className="btn btn-primary"

              onClick={() => setPhase("setup")}

            >

              Làm bài mới

            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={examMode === "mixed45" ? startMixedExam : startQuiz}
            >
              {examMode === "mixed45"
                ? `Thi lại ${PRACTICE_EXAM_SIZE} câu`
                : "Làm lại"}
            </button>

          </div>

        </section>

      )}

    </div>

  );

}


