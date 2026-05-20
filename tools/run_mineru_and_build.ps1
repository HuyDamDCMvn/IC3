# Chạy MinerU trên toàn bộ PDF rồi build ngân hàng câu hỏi visual
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path "data\ic3_unlocked.pdf")) {
    python -c "
from pypdf import PdfReader, PdfWriter
r = PdfReader(r'c:\Users\Acer\Downloads\On Thi IC3 GS6 SPARK LV1-Pass.pdf')
r.decrypt('ttthaqv')
w = PdfWriter()
for p in r.pages: w.add_page(p)
open('data/ic3_unlocked.pdf','wb').write(w)
print('Created data/ic3_unlocked.pdf')
"
}

Write-Host "=== MinerU: trich xuat PDF (co the mat 30-60 phut) ==="
mineru -p "data\ic3_unlocked.pdf" -o "data\mineru_out_full" -b pipeline -m ocr -l ch -s 1 -e 68 -f false -t false

Write-Host "=== Build quiz visual ==="
python tools\build_quiz_from_mineru.py

Write-Host "Done. Mo: cd apps\quiz-web; npm run dev"
