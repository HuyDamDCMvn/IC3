# IC3 GS6 Spark LV1 — Quiz Solution

Solution luyện trắc nghiệm từ tài liệu **On Thi IC3 GS6 SPARK LV1-Pass.pdf** (đáp án = tick xanh).

## Cấu trúc

```
packages/
  ic3-quiz-core/      # Thư viện TypeScript: chấm điểm, hiển thị đúng/sai
  ic3-answer-detect/  # Thư viện Python: nhận diện tick xanh trên ảnh PDF
apps/
  quiz-web/           # Ứng dụng web luyện đề
data/
  questions.json      # Ngân hàng câu hỏi + đáp án đúng
tools/
  extract_questions.py    # Trích xuất tự động (OCR + màu xanh)
  build_question_bank.py  # Tạo bộ câu curated
```

## Chạy ứng dụng luyện thi

```bash
cd apps/quiz-web
npm install
npm run dev
```

Mở http://localhost:5173 — chọn chủ đề, làm bài, bấm **Kiểm tra đáp án** để thấy đúng/sai ngay, cuối bài xem **điểm %** và chi tiết.

## Thư viện `@ic3-quiz/core`

```ts
import { gradeAnswer, getCorrectOptionIds, loadQuestionBank } from "@ic3-quiz/core";

const result = gradeAnswer(question, ["B"]);
// result.isCorrect, result.message, result.correctIds
```

## Trích xuất bằng MinerU (hình ảnh + câu hỏi giống PDF)

Cần cài: `pip install "mineru[core]"` — repo: https://github.com/opendatalab/MinerU

```powershell
# Toàn bộ PDF (trang 2–69)
.\tools\run_mineru_and_build.ps1

# Hoặc thủ công:
mineru -p data/ic3_unlocked.pdf -o data/mineru_out_full -b pipeline -m ocr -l ch -s 1 -e 68 -f false -t false
python tools/build_quiz_from_mineru.py
```

App web tự load `data/quiz-visual/questions.json` (có ảnh MinerU) + `data/questions.json` (text).

## Cập nhật câu hỏi text thủ công

`python tools/build_question_bank.py`

## Mật khẩu PDF

Chỉ dùng nội bộ; không commit mật khẩu vào git.
