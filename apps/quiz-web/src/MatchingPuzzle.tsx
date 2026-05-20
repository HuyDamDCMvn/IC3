import { useEffect, useMemo, useState } from "react";
import type { MatchingData } from "@ic3-quiz/core";

type Props = {
  data: MatchingData;
  revealed: boolean;
  rowResults?: Record<string, boolean>;
  userMap: Record<string, string>;
  onMapChange: (map: Record<string, string>) => void;
};

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function MatchingPuzzle({
  data,
  revealed,
  rowResults = {},
  userMap,
  onMapChange,
}: Props) {
  const [pool, setPool] = useState(() => shuffle(data.terms));
  const [dragTermId, setDragTermId] = useState<string | null>(null);

  useEffect(() => {
    setPool(shuffle(data.terms));
  }, [data]);

  const assignedTermIds = useMemo(
    () => new Set(Object.values(userMap)),
    [userMap]
  );

  const poolVisible = pool.filter((t) => !assignedTermIds.has(t.id));

  const assign = (defId: string, termId: string | null) => {
    const next = { ...userMap };
    if (termId) {
      for (const [d, t] of Object.entries(next)) {
        if (t === termId) delete next[d];
      }
      next[defId] = termId;
    } else {
      delete next[defId];
    }
    onMapChange(next);
  };

  const onDragStart = (termId: string) => (e: React.DragEvent) => {
    if (revealed) return;
    setDragTermId(termId);
    e.dataTransfer.setData("text/term-id", termId);
    e.dataTransfer.effectAllowed = "move";
  };

  const onDropDef = (defId: string) => (e: React.DragEvent) => {
    e.preventDefault();
    if (revealed) return;
    const termId = e.dataTransfer.getData("text/term-id");
    if (termId) assign(defId, termId);
    setDragTermId(null);
  };

  const termById = (id: string) => data.terms.find((t) => t.id === id);

  return (
    <div className="matching-puzzle">
      <div className="matching-instruction">{data.instruction}</div>

      <div className="matching-rows">
        {data.definitions.map((def) => {
          const termId = userMap[def.id];
          const term = termId ? termById(termId) : null;
          const rowOk = rowResults[def.id];
          const rowClass = revealed
            ? rowOk
              ? "row-correct"
              : termId
                ? "row-wrong"
                : ""
            : termId
              ? "row-filled"
              : "";

          return (
            <div
              key={def.id}
              className={`matching-row ${rowClass}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDropDef(def.id)}
            >
              <div className="puzzle-def">
                <span className="puzzle-num def-num">{def.id}</span>
                <span className="puzzle-text">{def.text}</span>
                <span className="puzzle-notch" aria-hidden />
              </div>
              <div
                className={`puzzle-term-slot ${term ? "has-term" : "empty"}`}
              >
                {term ? (
                  <div
                    className="puzzle-term"
                    draggable={!revealed}
                    onDragStart={onDragStart(term.id)}
                    onClick={() => !revealed && assign(def.id, null)}
                    title={revealed ? undefined : "Bấm để gỡ"}
                  >
                    <span className="puzzle-num term-num">{term.id}</span>
                    <span className="puzzle-text">{term.text}</span>
                  </div>
                ) : (
                  <span className="drop-hint">Kéo thuật ngữ vào đây</span>
                )}
                {revealed && termId && (
                  <span className="row-status">
                    {rowOk ? "✓" : "✗"}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {!revealed && poolVisible.length > 0 && (
        <div className="matching-pool">
          <p className="pool-label">Thuật ngữ — kéo sang ô bên trái:</p>
          <div className="pool-chips">
            {poolVisible.map((t) => (
              <div
                key={t.id}
                className={`pool-chip ${dragTermId === t.id ? "dragging" : ""}`}
                draggable
                onDragStart={onDragStart(t.id)}
              >
                <span className="puzzle-num term-num">{t.id}</span>
                {t.text}
              </div>
            ))}
          </div>
        </div>
      )}

      {revealed && (
        <div className="matching-answer-key">
          Đáp án:{" "}
          {data.definitions
            .map((d) => {
              const tid = data.correctMap[d.id];
              const t = termById(tid);
              return `${d.id} → ${tid}${t ? ` (${t.text})` : ""}`;
            })
            .join(" · ")}
        </div>
      )}
    </div>
  );
}
