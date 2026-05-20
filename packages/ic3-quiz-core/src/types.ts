export type YesNoLabelMode = "co-khong" | "dung-sai" | "fact-opinion";

export type QuestionType =
  | "single"
  | "multiple"
  | "truefalse"
  | "yesno"
  | "matching";

export interface MatchItem {
  id: string;
  text: string;
}

export interface MatchingData {
  instruction: string;
  definitions: MatchItem[];
  terms: MatchItem[];
  correctMap: Record<string, string>;
}

export interface QuizOption {
  id: string;
  text: string;
  isCorrect: boolean;
  imageUrl?: string;
}

export interface QuizQuestion {
  id: string;
  topic: string;
  testId: string;
  prompt: string;
  type: QuestionType;
  options: QuizOption[];
  page?: number;
  indexInTest?: number;
  totalInTest?: number;
  /** Full question crop — MinerU/PDF snapshot */
  snapshotUrl?: string;
  /** Extra images from MinerU extraction */
  images?: string[];
  /** Ghép mảnh: định nghĩa ↔ thuật ngữ */
  matching?: MatchingData;
  /** Có/Không hoặc Đúng/Sai */
  yesNoMode?: YesNoLabelMode;
}

export interface QuestionBank {
  version: number;
  source: string;
  theme?: string;
  total: number;
  questions: QuizQuestion[];
}

export interface GradeResult {
  isCorrect: boolean;
  selectedIds: string[];
  correctIds: string[];
  message: string;
}

export interface QuizSessionResult {
  total: number;
  correct: number;
  wrong: number;
  scorePercent: number;
  details: Array<{
    questionId: string;
    prompt: string;
    isCorrect: boolean;
    selectedIds: string[];
    correctIds: string[];
  }>;
}
