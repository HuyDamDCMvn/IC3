/**
 * Fix garbled Vietnamese diacritics from MinerU OCR.
 * Maps OCR-garbled words to correct Vietnamese.
 */
const fs = require('fs');

const WORD_MAP = {
  // ā → ã/ạ patterns
  "hāy": "hãy", "Hāy": "Hãy", "Hǎy": "Hãy", "hǎy": "hãy",
  "dā": "đã", "đā": "đã",
  "xā": "xã", "xǎ": "xã",
  "māt": "mật", "māu": "mẫu", "māp": "mập",
  "sān": "sản",
  "lāng": "lãng",
  "dān": "dân", "giān": "gian",
  "chuān": "chuẩn", "thuāt": "thuật",
  "luān": "luận", "luāng": "luận",

  // ě → ế/ể patterns
  "biět": "biết", "Biět": "Biết",
  "thiět": "thiết", "Thiět": "Thiết",
  "thiēt": "thiết",
  "viět": "viết",
  "kiěm": "kiểm",
  "kiēm": "kiểm",
  "hiěn": "hiển", "hiēn": "hiện",
  "diěn": "điền", "diēn": "điện",
  "diěu": "điều", "Diěu": "Điều",
  "tiěn": "tiện", "tiēn": "tiến",
  "tiěng": "tiếng",
  "tiěp": "tiếp", "tiēp": "tiếp",
  "truyěn": "truyền", "Truyěn": "Truyền",
  "tuyěn": "tuyến",
  "chuyěn": "chuyển",
  "quyěn": "quyền", "Quyěn": "Quyền",
  "quyết": "quyết", "quyět": "quyết",
  "niěm": "niệm",
  "chiěn": "chiến", "chiěu": "chiếu", "chiěc": "chiếc",
  "biēt": "biệt", "biēu": "biểu", "biěu": "biểu",
  "miěn": "miễn",
  "khiěn": "khiến", "khiēn": "khiến",
  "liēn": "liên",
  "kě": "kể",

  // ē → ế/ề/ê patterns
  "trēn": "trên", "Trēn": "Trên",
  "nēn": "nên",
  "nēu": "nếu",
  "dē": "để", "đē": "để", "dēn": "đến", "đēn": "đến",
  "dě": "để", "đě": "để", "děn": "đến", "đěn": "đến",
  "děu": "đều",
  "kēt": "kết", "k\u011bt": "kết", "K\u011bt": "Kết",
  "hět": "hết",
  "sē": "sẽ", "sě": "sẽ",
  "thē": "thể", "thěm": "thêm", "thēm": "thêm",
  "lě": "lệ", "Lě": "Lệ",
  "bě": "bể",
  "tě": "tế",
  "vě": "về",
  "yēu": "yêu", "yěu": "yếu",
  "nǎi": "nại",

  // ō → ố/ồ/ô patterns
  "thōng": "thông", "Thōng": "Thông",
  "khōng": "không", "Khōng": "Không",
  "dōng": "đồng",
  "Cōng": "Công", "cōng": "công",
  "sōng": "sống",
  "mōi": "mới",
  "nōi": "nối",
  "giōng": "giống",
  "huōng": "hưởng", "xuōng": "xuống",
  "muōn": "muốn", "muön": "muốn", "muǒn": "muốn",

  // ǒ → ổ/ỗ/ố patterns
  "mǒi": "mỗi",
  "sǒ": "số", "sö": "số",
  "Nhiēm": "Nhiễm",
  "cǒ": "cổ", "Cǒ": "Cổ",
  "gǒm": "gồm",
  "ngǒi": "ngồi",
  "rǒi": "rồi",
  "chuǒi": "chuỗi",
  "cuǎi": "cuối",

  // ǎ → ắ/ằ/ặ/ă patterns (Vietnamese ă with tones)
  "dǎng": "đăng", "Dǎng": "Đăng", "đǎng": "đăng",
  "bǎt": "bắt", "Bǎt": "Bắt",
  "dǎt": "đặt", "Dǎt": "Đặt",
  "nǎng": "năng",
  "nǎm": "năm",
  "vǎn": "văn",
  "vǎi": "với",
  "mǎi": "mãi",
  "mǎt": "mặt",
  "mǎu": "mẫu",
  "cǎn": "cần", "cǎm": "cảm",
  "cǎp": "cấp", "cǎu": "câu",
  "tǎm": "tắm", "tǎng": "tăng", "Tǎng": "Tăng", "tǎt": "tắt",
  "chǎm": "chậm", "chǎn": "chắn", "chǎng": "chẳng",
  "dǎ": "đã",
  "dǎc": "đặc",
  "dǎn": "đẫn",
  "gǎn": "gần", "gǎng": "gắng", "gǎp": "gặp",
  "lǎn": "lần",
  "nhǎc": "nhắc", "nhǎm": "nhằm", "nhǎn": "nhắn", "nhǎt": "nhất",
  "phǎn": "phần", "phǎng": "phẳng",
  "sǎc": "sắc",
  "thǎi": "thải", "thǎm": "thắm", "thǎng": "thẳng", "thǎy": "thấy",
  "xǎu": "xấu",
  "ǎn": "ăn", "ǎy": "ấy",

  // ü → ư patterns
  "nhüng": "nhưng", "Nhüng": "Nhưng",
  "nhǔng": "những", "Nhǔng": "Những", "nhǔǐng": "những",
  "giü": "giữ", "Giü": "Giữ",
  "güi": "gửi", "Güi": "Gửi",
  "dü": "dữ", "Dü": "Dữ",
  "hüu": "hữu", "hǔu": "hữu",
  "lüa": "lừa",
  "trü": "trữ", "trǔ": "trữ",
  "chü": "chữ", "Chü": "Chữ",
  "ngü": "ngữ", "ngǔ": "ngữ", "ngǔ'": "ngữ",
  "büa": "bữa",
  "tǔng": "từng",

  // ö → ơ/ổ patterns
  "nguöi": "người", "Nguöi": "Người",
  "nguön": "nguồn",
  "thuöc": "thuộc",
  "cuöi": "cuối", "cuön": "cuốn",
  "löi": "lỗi", "Löi": "Lỗi",
  "döi": "đổi",
  "dön": "đơn",
  "röi": "rồi",

  // δ → ổ patterns
  "sδ": "số",
  "Tuδi": "Tuổi",
  "N∂i": "Nội",

  // ∂ → ộ/ọ patterns
  "M∂t": "Một",

  // Common full-word fixes (no special chars but wrong Vietnamese)
  "Ban": "Bạn", // Only at sentence start when meaning "you"
  "dàu": "dấu",
  "thi": "thi",

  // ǔ → ủ/ử/ữ
  "chǔ": "chữ", "chǔ'": "chữ",
  "cǔng": "cũng",

  // Additional fixes
  "Cüa": "Của", "giüa": "giữa",
  "ngǎi": "ngại", "ngǎn": "ngắn",
  "sō": "số",
  "Thě": "Thể", "thě": "thể",

  // Mixed
  "měm": "mềm", "měn": "mến",
  "Nghiēng": "Nghiêng",
  "Kiēu": "Kiểu", "kiēu": "kiểu",
  "kiēn": "kiến", "kiěn": "kiến",
  "viēc": "việc", "viēn": "viện",
  "hoǎc": "hoặc",
  "söng": "sống",
  "iě": "iệ",
  "xěp": "xếp",
  "gō": "gõ",
  "tō": "tổ",
  "hō": "hỗ", "Hǒ": "Hỗ",
  "Döng": "Đồng",
  "dět": "đặt",
  "Dě": "Để",
  "Dǎi": "Dải",
  "něu": "nếu",
  "Tiěn": "Tiền",
  "Thuyết": "Thuyết", "Thuyět": "Thuyết",
  "3sö": "số",
  "diēm": "điểm",
};

// Phase 2: common Vietnamese words with wrong/missing diacritics
const PHRASE_MAP = [
  // Multi-word phrases (order matters - longer first)
  ["mang xa hoi", "mạng xã hội"], ["mang xã hội", "mạng xã hội"],
  ["mang xā hòi", "mạng xã hội"], ["mang xǎ hòi", "mạng xã hội"],
  ["mang xã hòi", "mạng xã hội"],
  ["ky nghi hè", "kỳ nghỉ hè"],
  ["ky thuật số", "kỹ thuật số"], ["kỹ thuật số", "kỹ thuật số"],
  ["may tinh bang", "máy tính bảng"], ["máy tính bang", "máy tính bảng"],
  ["máy tinh xách tay", "máy tính xách tay"],
  ["bàn do", "bản đồ"],
  ["bàn phím", "bàn phím"],
  ["cong nghè", "công nghệ"], ["Còng nghè", "Công nghệ"],
  ["ngày mai", "ngày mai"],
  ["ky thuat so", "kỹ thuật số"], ["ky thuàt sō", "kỹ thuật số"],
  ["ky thuàt sö", "kỹ thuật số"],
  ["trinh duyet", "trình duyệt"], ["trinh duyèt", "trình duyệt"],
  ["dinh dang", "định dạng"],
  ["dinh nghia", "định nghĩa"],
  ["thiet bi", "thiết bị"], ["thiět bị", "thiết bị"],
  ["may tinh", "máy tính"], ["máy tinh", "máy tính"],
  ["phan mem", "phần mềm"], ["phàn měm", "phần mềm"],
  ["mat khau", "mật khẩu"], ["mat khàu", "mật khẩu"],
  ["thu dien tu", "thư điện tử"], ["thu điện tù", "thư điện tử"],
  ["thu dièn tù", "thư điện tử"], ["Thu dièn tù", "Thư điện tử"],
  ["Thu diēn tùr", "Thư điện tử"], ["Thu diēn tù", "Thư điện tử"],
  ["tin nhǎn", "tin nhắn"], ["tin nhán", "tin nhắn"],
  ["bàn di chuòt", "bàn di chuột"],
  ["dia chi", "địa chỉ"],
  ["trang Web", "trang Web"],
  ["phòng chữ", "phông chữ"],
  ["hoc sinh", "học sinh"],
  ["giáo vièn", "giáo viên"], ["giáo viēn", "giáo viên"],
  ["truc tuyěn", "trực tuyến"], ["truc tuyến", "trực tuyến"],
  ["cài dǎt", "cài đặt"], ["cài dat", "cài đặt"],
  ["buu dièn", "bưu điện"],
  ["lich su'", "lịch sử"], ["lich sù'", "lịch sử"],
];

// Single word fixes (safe contextual replacements)
const WORD_MAP_2 = {
  "sù'": "sử", "du'": "dụ",
  "thuàt": "thuật", "thuat": "thuật",
  "ngữ'": "ngữ",
  "dúng": "đúng",
  "cúa": "của",
  "bèn": "bên",
  "tùng": "từng",
  "tù": "từ",
  "nèn": "nên",
  "khòng": "không",
  "chon": "chọn",
  "mòt": "một", "Mot": "Một",
  "dó": "đó",
  "lài": "lại",
  "phài": "phải",
  "hop": "hợp",
  "thich": "thích",
  "duoc": "được", "dudc": "được",
  "nguài": "người",
  "nhàp": "nhập",
  "nhàn": "nhận",
  "doan": "đoạn",
  "giò": "giờ",
  "häy": "hãy",
  "dàu": "dấu",
  "hgp": "hợp",
  "thòi": "thời",
  "luong": "lượng",
  "tuong": "tương",
  "thuong": "thương",
  "chuong": "chương",
  "truong": "trường",
  "duong": "đường",
  "tiính": "tính",
  "dièn": "điện",
  "luu": "lưu",
  "dày": "đây",
  "ngoai": "ngoại",
  "bi": "bị",
  "dinh": "định",
  "dung": "dụng",
  "tot": "tốt",
  "cong": "công",
  "dàn": "dân",
  "dät": "đặt",
  "luàn": "luận",
  "chuyèn": "chuyện",
  "cuòc": "cuộc",
  "dièu": "điều",
  "nguài": "người",
  "nghè": "nghệ",
  "tièu": "tiêu",
  "hiēu": "hiệu",
  "kiěu": "kiểu",
  "chiēu": "chiều",
  "tièn": "tiền",
  "nghiēm": "nghiệm",
  "liēu": "liệu",
  "vièc": "việc",
  "dōi": "đội",
  "lièu": "liệu",
  "nghièn": "nghiên",
  "diēm": "điểm",
  "hiēu": "hiệu",
  "kiēn": "kiến",
  "chieu": "chiếu",
  "lop": "lớp",
  "quà": "quả",
  "dè": "để",
  "trinh": "trình",
  "duyèt": "duyệt",
  "Chon": "Chọn",
  "cùa": "của",
  "tièng": "tiếng",
  "phän": "phần",
  "lièu": "liệu",
  "dang": "đang",
  "tryc": "trực",
  "dugc": "được",
  "dyng": "dựng",
  "muon": "muốn",
  "phuong": "phương",
  "phich": "phích",
  "thoai": "thoại",
  "nhung": "nhưng",
  "trèn": "trên",
  "minh": "mình",
  "cua": "của",
  "doi": "đối", "Doi": "Đối",
  "vói": "với",
  "dúng": "đúng", "Dúng": "Đúng",
  "còng": "công",
  "giáo": "giáo",
  "tèn": "tên",
  "dài": "đại",
  "giào": "giáo",
  "hòi": "hội",
  "gùi": "gửi",
  "phu": "phụ",
  "ràng": "rằng",
  "yèu": "yêu",
  "trèn": "trên",
  "nhò": "nhở",
  "budi": "buổi",
  "thdi": "thời",
  "ngudi": "người", "ngui": "người",
  "chdi": "chơi",
  "bieu": "biểu",
  "hoat": "hoạt",
  "dòng": "động",
  "muc": "mục", "Muc": "Mục",
  "dich": "đích",
  "thyc": "thực",
  "gian": "gian",
  "kiem": "kiểm",
  "nghia": "nghĩa",
};

function fixText(text) {
  if (!text) return text;
  let result = text;

  // Phase 1: Apply garbled char word-level replacements
  for (const [wrong, correct] of Object.entries(WORD_MAP)) {
    const escaped = wrong.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(?<![\\p{L}])${escaped}(?![\\p{L}])`, 'gu');
    result = result.replace(re, correct);
  }

  // Phase 2: Multi-word phrase replacements
  for (const [wrong, correct] of PHRASE_MAP) {
    const escaped = wrong.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(escaped, 'gi');
    result = result.replace(re, correct);
  }

  // Phase 3: Single word replacements (be careful with context)
  for (const [wrong, correct] of Object.entries(WORD_MAP_2)) {
    const escaped = wrong.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(?<![\\p{L}])${escaped}(?![\\p{L}])`, 'gu');
    result = result.replace(re, correct);
  }

  return result;
}

// Load and fix
const files = [
  'data/questions-merged.json',
  'data/quiz-visual/questions.json',
];

for (const file of files) {
  const path = file;
  if (!fs.existsSync(path)) continue;

  const data = JSON.parse(fs.readFileSync(path, 'utf8'));
  let totalFixes = 0;

  for (const q of data.questions) {
    const origPrompt = q.prompt;
    q.prompt = fixText(q.prompt);
    if (q.prompt !== origPrompt) totalFixes++;

    for (const o of (q.options || [])) {
      const origText = o.text;
      o.text = fixText(o.text);
      if (o.text !== origText) totalFixes++;
    }
  }

  fs.writeFileSync(path, JSON.stringify(data, null, 2), 'utf8');
  console.log(`${file}: ${totalFixes} text fixes applied`);
}

// Verify remaining issues
const data = JSON.parse(fs.readFileSync('data/questions-merged.json', 'utf8'));
let allText = '';
for (const q of data.questions) {
  allText += q.prompt + '\n';
  for (const o of (q.options || [])) allText += (o.text || '') + '\n';
}
const suspiciousRe = /[\u0101\u011b\u0113\u014d\u01d2\u01ce\u03b4\u00fc\u00f6\u01d6\u01d4\u2202]/;
const words = allText.split(/[\s,.()\[\]"\/\-!?:;]+/).filter(Boolean);
const remaining = new Set();
for (const w of words) {
  if (suspiciousRe.test(w) && w.length > 1) remaining.add(w);
}
console.log(`\nRemaining garbled words: ${remaining.size}`);
if (remaining.size > 0) {
  [...remaining].sort().forEach(w => console.log(' ', w));
}
