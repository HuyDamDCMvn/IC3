import { useMemo, useState } from "react";
import {
  filterQuestions,
  getMatchingData,
  getTestsForTopic,
  getTopics,
  isMatchingQuestion,
  isYesNoQuestion,
} from "@ic3-quiz/core";
import type { QuizQuestion } from "@ic3-quiz/core";
import { QuestionCard } from "./QuestionCard";

const TOPIC_LABELS: Record<string, string> = {
  "topic-1": "Chủ đề 1 — Phần cứng & thiết bị",
  "topic-2": "Chủ đề 2 — Công dân số",
  "topic-3": "Chủ đề 3 — Internet & tìm kiếm",
  "topic-4": "Chủ đề 4 — Ứng dụng văn phòng",
  "topic-5": "Chủ đề 5 — Giao tiếp số",
  "topic-6": "Chủ đề 6 — An toàn & thiết bị",
  "topic-extended": "Chủ đề mở rộng",
};

const TYPE_LABELS: Record<string, string> = {
  single: "Trắc nghiệm",
  multiple: "Chọn nhiều",
  matching: "Ghép mảnh",
  yesno: "Dropdown (Có/Không, Đúng/Sai, Thực tế/Ý kiến)",
  truefalse: "Đúng / Sai",
};

function sortQuestions(a: QuizQuestion, b: QuizQuestion): number {
  const t = a.topic.localeCompare(b.topic);
  if (t !== 0) return t;
  const td = a.testId.localeCompare(b.testId);
  if (td !== 0) return td;
  return (a.indexInTest ?? 999) - (b.indexInTest ?? 999);
}

function correctIds(q: QuizQuestion): string[] {
  return q.options.filter((o) => o.isCorrect).map((o) => o.id);
}

export function getInspectIssues(q: QuizQuestion): string[] {
  const issues: string[] = [];
  if (!q.prompt?.trim()) issues.push("Thiếu đề bài");
  if (q.options.length === 0) issues.push("Không có đáp án");
  if (isMatchingQuestion(q)) {
    if (!getMatchingData(q)) issues.push("Thiếu dữ liệu ghép mảnh");
    return issues;
  }
  if (isYesNoQuestion(q)) {
    if (q.options.length < 1) issues.push("Thiếu mệnh đề");
    for (const o of q.options) {
      if (!o.text?.trim() || o.text.length < 6) {
        issues.push("Mệnh đề OCR lỗi");
        break;
      }
    }
    return issues;
  }
  if (q.type === "single" && q.options.length < 2) {
    issues.push("Ít hơn 2 lựa chọn");
  }
  if (q.type === "multiple" && q.options.length < 2) {
    issues.push("Ít hơn 2 lựa chọn");
  }
  const correct = correctIds(q);
  if (correct.length === 0) issues.push("Chưa có đáp án đúng");
  if (correct.length >= 2 && q.type !== "multiple") {
    issues.push(`${correct.length} tick xanh nhưng type=single`);
  }
  if (q.type === "multiple" && correct.length > 0 && correct.length < 2) {
    issues.push("Multiple nhưng chỉ 1 tick xanh");
  }
  return issues;
}

type Props = {
  bank: QuizQuestion[];
};

export function InspectTab({ bank }: Props) {
  const [topic, setTopic] = useState("");
  const [testId, setTestId] = useState("");
  const [search, setSearch] = useState("");
  const [issuesOnly, setIssuesOnly] = useState(false);
  const [hideAnswers, setHideAnswers] = useState(false);
  const [showToc, setShowToc] = useState(true);

  const sortedBank = useMemo(() => [...bank].sort(sortQuestions), [bank]);

  const tests = useMemo(
    () => (topic ? getTestsForTopic(sortedBank, topic) : []),
    [sortedBank, topic]
  );

  const list = useMemo(() => {
    let qs = filterQuestions(sortedBank, {
      topic: topic || undefined,
      testId: testId || undefined,
      limit: 0,
      shuffle: false,
    });
    if (search.trim()) {
      const s = search.toLowerCase();
      qs = qs.filter(
        (q) =>
          q.prompt.toLowerCase().includes(s) ||
          q.options.some((o) => o.text.toLowerCase().includes(s)) ||
          `${q.indexInTest ?? ""}`.includes(s)
      );
    }
    if (issuesOnly) {
      qs = qs.filter((q) => getInspectIssues(q).length > 0);
    }
    return qs;
  }, [sortedBank, topic, testId, search, issuesOnly]);

  const stats = useMemo(() => {
    const issueCount = sortedBank.filter(
      (q) => getInspectIssues(q).length > 0
    ).length;
    return {
      total: sortedBank.length,
      single: sortedBank.filter((q) => q.type === "single").length,
      multiple: sortedBank.filter((q) => q.type === "multiple").length,
      matching: sortedBank.filter((q) => q.type === "matching").length,
      yesno: sortedBank.filter((q) => isYesNoQuestion(q)).length,
      issues: issueCount,
    };
  }, [sortedBank]);

  const byTopicTest = useMemo(() => {
    const map = new Map<string, Map<string, QuizQuestion[]>>();
    for (const q of list) {
      if (!map.has(q.topic)) map.set(q.topic, new Map());
      const testsMap = map.get(q.topic)!;
      if (!testsMap.has(q.testId)) testsMap.set(q.testId, []);
      testsMap.get(q.testId)!.push(q);
    }
    return map;
  }, [list]);

  function scrollToQuestion(id: string) {
    document.getElementById(`inspect-${id}`)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function yesNoMapFor(q: QuizQuestion): Record<string, "yes" | "no"> {
    if (hideAnswers || !isYesNoQuestion(q)) return {};
    const map: Record<string, "yes" | "no"> = {};
    for (const o of q.options) {
      map[o.id] = o.isCorrect ? "yes" : "no";
    }
    return map;
  }

  function matchingMapFor(q: QuizQuestion): Record<string, string> {
    if (hideAnswers || !isMatchingQuestion(q)) return {};
    const m = getMatchingData(q);
    if (!m) return {};
    const inv: Record<string, string> = {};
    for (const [defId, termId] of Object.entries(m.correctMap)) {
      inv[defId] = termId;
    }
    return inv;
  }

  return (
    <section className="inspect-tab">
      <div className="card inspect-toolbar">
        <h2 className="inspect-title">Kiểm tra ngân hàng câu hỏi</h2>
        <p className="inspect-desc">
          Xem toàn bộ {stats.total} câu: đề, ảnh PDF, đáp án đúng (tick xanh). Dùng
          bộ lọc và mục lục để rà nhanh.
        </p>

        <div className="inspect-stats">
          <span>
            <strong>{stats.total}</strong> câu
          </span>
          <span>{stats.single} chọn 1</span>
          <span>{stats.multiple} chọn nhiều</span>
          <span>{stats.matching} ghép</span>
          <span>{stats.yesno} có/không</span>
          <span className={stats.issues > 0 ? "inspect-stat-warn" : ""}>
            {stats.issues} cần xem lại
          </span>
        </div>

        <input
          type="search"
          className="review-search"
          placeholder="Tìm đề / đáp án / số câu…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <div className="inspect-toolbar-row">
          <label>
            <input
              type="checkbox"
              checked={issuesOnly}
              onChange={(e) => setIssuesOnly(e.target.checked)}
            />{" "}
            Chỉ câu có vấn đề ({stats.issues})
          </label>
          <label>
            <input
              type="checkbox"
              checked={hideAnswers}
              onChange={(e) => setHideAnswers(e.target.checked)}
            />{" "}
            Ẩn đáp án
          </label>
          <label>
            <input
              type="checkbox"
              checked={showToc}
              onChange={(e) => setShowToc(e.target.checked)}
            />{" "}
            Mục lục
          </label>
        </div>

        <div className="inspect-filters-grid">
          <div>
            <label>Chủ đề</label>
            <select
              value={topic}
              onChange={(e) => {
                setTopic(e.target.value);
                setTestId(
                  getTestsForTopic(sortedBank, e.target.value)[0] ?? ""
                );
              }}
            >
              <option value="">Tất cả</option>
              {getTopics(sortedBank).map((t) => (
                <option key={t} value={t}>
                  {TOPIC_LABELS[t] ?? t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Bài test</label>
            <select
              value={testId}
              onChange={(e) => setTestId(e.target.value)}
              disabled={!topic}
            >
              <option value="">Tất cả</option>
              {tests.map((t) => (
                <option key={t} value={t}>
                  {t.replace("test-", "Test ")}
                </option>
              ))}
            </select>
          </div>
        </div>

        <p className="review-count">
          Đang hiển thị <strong>{list.length}</strong> câu
        </p>
      </div>

      <div className="inspect-body">
        {showToc && list.length > 0 && (
          <aside className="inspect-toc card">
            <h3 className="inspect-toc-title">Mục lục</h3>
            <ul className="inspect-toc-list">
              {list.map((q) => {
                const issues = getInspectIssues(q);
                const label =
                  q.indexInTest != null
                    ? `Q${q.indexInTest}`
                    : `#${list.indexOf(q) + 1}`;
                return (
                  <li key={q.id}>
                    <button
                      type="button"
                      className={`inspect-toc-btn ${issues.length ? "has-issue" : ""}`}
                      onClick={() => scrollToQuestion(q.id)}
                      title={q.prompt.slice(0, 80) || "(không có đề)"}
                    >
                      <span className="inspect-toc-label">{label}</span>
                      <span className="inspect-toc-meta">
                        {q.testId.replace("test-", "T")}
                      </span>
                      {issues.length > 0 && <span className="inspect-toc-warn">!</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>
        )}

        <div className="inspect-list">
          {list.length === 0 && (
            <p className="loading card">Không có câu phù hợp bộ lọc.</p>
          )}

          {[...byTopicTest.entries()].map(([t, testsMap]) => (
            <div key={t} className="inspect-topic-block">
              <h3 className="review-group-title">
                {TOPIC_LABELS[t] ?? t}
              </h3>
              {[...testsMap.entries()].map(([test, questions]) => (
                <div key={`${t}-${test}`} className="inspect-test-block">
                  <h4 className="inspect-test-title">
                    {test.replace("test-", "Test ")} · {questions.length} câu
                  </h4>
                  {questions.map((q, i) => {
                    const issues = getInspectIssues(q);
                    return (
                      <div
                        key={q.id}
                        id={`inspect-${q.id}`}
                        className="inspect-item"
                      >
                        <header className="inspect-item-head">
                          <div className="inspect-item-ids">
                            <span className="inspect-item-badge">
                              {TOPIC_LABELS[q.topic] ?? q.topic}
                            </span>
                            <span>
                              {q.testId.replace("test-", "Test ")}
                              {q.indexInTest != null &&
                                ` · Câu ${q.indexInTest}/${q.totalInTest ?? "?"}`}
                            </span>
                            <span className="inspect-type">
                              {TYPE_LABELS[q.type] ?? q.type}
                            </span>
                            {q.page != null && (
                              <span>Trang PDF {q.page}</span>
                            )}
                          </div>
                          {issues.length > 0 && (
                            <ul className="inspect-issues">
                              {issues.map((msg) => (
                                <li key={msg}>{msg}</li>
                              ))}
                            </ul>
                          )}
                        </header>
                        <QuestionCard
                          question={q}
                          index={i}
                          revealed={!hideAnswers}
                          selected={[]}
                          matchingMap={matchingMapFor(q)}
                          yesNoAnswers={yesNoMapFor(q)}
                          showMeta={false}
                        />
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
