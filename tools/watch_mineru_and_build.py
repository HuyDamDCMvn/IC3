"""
Theo doi MinerU, bao cao moi 10 phut, tu build quiz khi xong.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "mineru_watch.log"
TERMINAL_LOG = Path(
    r"C:\Users\Acer\.cursor\projects\d-03-DCMvn-IC3\terminals\898017.txt"
)
MINERU_FULL = ROOT / "data" / "mineru_out_full" / "ic3_unlocked" / "ocr"
CONTENT_LIST = MINERU_FULL / "ic3_unlocked_content_list.json"
REPORT_INTERVAL_SEC = 600  # 10 minutes


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def tail_terminal(n: int = 8) -> str:
    if not TERMINAL_LOG.exists():
        return "(khong tim thay terminal log)"
    lines = TERMINAL_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


def parse_ocr_progress() -> str | None:
    if not TERMINAL_LOG.exists():
        return None
    text = TERMINAL_LOG.read_text(encoding="utf-8", errors="replace")
    for line in reversed(text.splitlines()):
        if "OCR-rec Predict" in line and "%" in line:
            return line.strip()
        if "Completed batch" in line or "MinerU completed" in line:
            return line.strip()
        if "Layout Predict" in line and "%" in line:
            return line.strip()
    return None


def is_mineru_done() -> bool:
    if CONTENT_LIST.exists():
        try:
            data = json.loads(CONTENT_LIST.read_text(encoding="utf-8"))
            if len(data) > 20:
                return True
        except Exception:
            pass
    if TERMINAL_LOG.exists():
        t = TERMINAL_LOG.read_text(encoding="utf-8", errors="replace")
        if "Completed batch" in t and "exit_code" not in t[-500:]:
            # check footer for exit
            if "exit_code: 0" in t or "Saved" in t:
                pass
        if "exit_code: 0" in t[-2000:] and "mineru" in t.lower():
            return True
        if "exit_code:" in t[-500:]:
            code_line = [l for l in t.splitlines() if "exit_code:" in l][-1]
            if "exit_code: 0" in code_line:
                return True
            if "exit_code:" in code_line and "exit_code: 0" not in code_line:
                return True  # finished with error still try build
    return CONTENT_LIST.exists()


def run_build() -> bool:
    log("=== BAT DAU BUILD QUIZ VISUAL ===")
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_quiz_from_mineru.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    log(r.stdout.strip() or "(no stdout)")
    if r.stderr:
        log("stderr: " + r.stderr.strip()[:500])
    if r.returncode != 0:
        log(f"BUILD LOI exit={r.returncode}")
        return False

    r2 = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "merge_question_banks.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    log(r2.stdout.strip() or "merge ok")
    return True


def count_questions() -> int:
    qf = ROOT / "data" / "quiz-visual" / "questions.json"
    if not qf.exists():
        return 0
    data = json.loads(qf.read_text(encoding="utf-8"))
    return data.get("total", len(data.get("questions", [])))


def main():
    log("WATCHER START — bao cao moi 10 phut")
    last_report = 0.0
    built = False

    while True:
        now = time.time()
        progress = parse_ocr_progress()
        done = is_mineru_done()

        if now - last_report >= REPORT_INTERVAL_SEC or last_report == 0:
            blocks = 0
            if CONTENT_LIST.exists():
                try:
                    blocks = len(
                        json.loads(CONTENT_LIST.read_text(encoding="utf-8"))
                    )
                except Exception:
                    pass
            log("--- BAO CAO 10 PHUT ---")
            log(f"Trang thai: {'HOAN TAT' if done else 'DANG CHAY'}")
            log(f"content_list blocks: {blocks}")
            log(f"questions visual hien co: {count_questions()}")
            if progress:
                log(f"Tien do: {progress}")
            log("Terminal (cuoi):\n" + tail_terminal(5))
            last_report = now

        if done and not built:
            ok = run_build()
            n = count_questions()
            log(f"=== BUILD XONG: {n} cau visual ===")
            built = True
            log("WATCHER KET THUC (MinerU da xong + da build)")
            return 0

        # Neu terminal co exit_code va khong con content_list, thoat
        if TERMINAL_LOG.exists():
            tail = TERMINAL_LOG.read_text(encoding="utf-8", errors="replace")[-3000:]
            if "exit_code:" in tail and not done:
                log("MinerU da dung (exit) nhung chua co content_list day du")
                if CONTENT_LIST.exists():
                    run_build()
                    built = True
                return 1

        time.sleep(60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
