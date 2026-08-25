"""Render lampiran markdown (D-G) menjadi PNG siap tempel ke dokumen proposal.

Alurnya: markdown -> HTML bergaya cetak -> PDF lewat Chrome headless -> PNG per
halaman lewat pypdfium2. Chrome dipakai karena dialah yang menangani pemenggalan
halaman A4 dengan benar; menyusun halaman sendiri lewat CSS mudah meleset.

Menjalankan: python docs/build_lampiran.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pypdfium2 as pdfium
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "lampiran"
TMP_DIR = OUT_DIR / "_tmp"

DPI = 150                       # 150 dpi -> A4 jadi 1240x1754 px, cukup tajam untuk dicetak
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

# (huruf lampiran, berkas sumber, judul yang dicetak di kepala halaman)
LAMPIRAN = [
    ("D", "docs/model_card.md", "Lampiran D — Model Card"),
    ("E", "docs/dataset_card.md", "Lampiran E — Dataset Card"),
    ("F", "docs/api_contract.md", "Lampiran F — Kontrak API"),
    ("G", "docs/feature_schema.md", "Lampiran G — Skema Fitur 12 Kolom"),
]

# Palet sama dengan grafik di ml/reports supaya lampiran terlihat satu keluarga
CSS = """
@page { size: A4; margin: 16mm 14mm 14mm 14mm; }
* { box-sizing: border-box; }
body {
  margin: 0; background: #fcfcfb; color: #0b0b0b;
  font-family: "Segoe UI", "Inter", system-ui, sans-serif;
  font-size: 9.6pt; line-height: 1.55;
}
.kepala {
  font-size: 8pt; letter-spacing: .08em; text-transform: uppercase;
  color: #52514e; border-bottom: 1px solid #e8e7e3;
  padding-bottom: 6px; margin-bottom: 18px;
}
h1 { font-size: 17pt; margin: 0 0 4px; letter-spacing: -.01em; }
h2 { font-size: 12.5pt; margin: 20px 0 6px; padding-top: 4px; border-top: 1px solid #e8e7e3; }
h3 { font-size: 10.5pt; margin: 14px 0 4px; }
h4 { font-size: 9.8pt; margin: 12px 0 4px; color: #52514e; }
h1, h2, h3, h4 { break-after: avoid; }
p, ul, ol { margin: 0 0 8px; }
li { margin-bottom: 2px; }
strong { font-weight: 650; }
code {
  font-family: "Cascadia Mono", Consolas, monospace; font-size: 8.6pt;
  background: #f1f0ec; padding: 1px 4px; border-radius: 3px;
}
pre {
  background: #f7f6f3; border: 1px solid #e8e7e3; border-radius: 4px;
  padding: 9px 11px; overflow-x: hidden;
}
pre code { background: none; padding: 0; font-size: 7.4pt; line-height: 1.38; white-space: pre; }
/* Diagram ASCII harus utuh satu baris; membungkusnya merusak gambarnya. */
blockquote {
  margin: 8px 0; padding: 2px 0 2px 12px;
  border-left: 3px solid #cde2fb; color: #52514e;
}
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.6pt; }
th, td { border: 1px solid #e8e7e3; padding: 5px 7px; text-align: left; vertical-align: top; }
th { background: #f1f0ec; font-weight: 650; }
tr { break-inside: avoid; }
hr { border: 0; border-top: 1px solid #e8e7e3; margin: 16px 0; }
a { color: #2a78d6; text-decoration: none; }
img { max-width: 100%; }
"""


def cari_chrome():
    for kandidat in CHROME_CANDIDATES:
        if Path(kandidat).exists():
            return kandidat
    sys.exit("Chrome/Edge tidak ditemukan — sesuaikan CHROME_CANDIDATES.")


def ke_html(md_path, judul):
    md = MarkdownIt().enable(["table", "strikethrough"])
    isi = md.render(Path(md_path).read_text(encoding="utf-8"))
    return (f"<!doctype html><html lang=\"id\"><head><meta charset=\"utf-8\">"
            f"<title>{judul}</title><style>{CSS}</style></head>"
            f"<body><div class=\"kepala\">{judul}</div>{isi}</body></html>")


def ke_pdf(chrome, html_path, pdf_path):
    subprocess.run([
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer", "--virtual-time-budget=4000",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ], check=True, capture_output=True)


def ke_png(pdf_path, prefiks):
    doc = pdfium.PdfDocument(pdf_path)
    hasil = []
    for i in range(len(doc)):
        keluaran = OUT_DIR / f"{prefiks}_hal{i + 1:02d}.png"
        doc[i].render(scale=DPI / 72).to_pil().save(keluaran)
        hasil.append(keluaran)
    doc.close()
    return hasil


def main():
    chrome = cari_chrome()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)

    # Bersihkan keluaran lama: jumlah halaman bisa berkurang, dan sisa berkas
    # halaman lama gampang ikut tertempel ke dokumen tanpa disadari.
    for usang in list(OUT_DIR.glob("lampiran_*.png")) + list(OUT_DIR.glob("lampiran_*.pdf")):
        usang.unlink()

    total = 0
    for huruf, sumber, judul in LAMPIRAN:
        nama = Path(sumber).stem
        html_path = TMP_DIR / f"{nama}.html"
        pdf_path = TMP_DIR / f"{nama}.pdf"
        html_path.write_text(ke_html(ROOT / sumber, judul), encoding="utf-8")
        ke_pdf(chrome, html_path, pdf_path)
        halaman = ke_png(pdf_path, f"lampiran_{huruf}_{nama}")
        shutil.copy(pdf_path, OUT_DIR / f"lampiran_{huruf}_{nama}.pdf")
        total += len(halaman)
        print(f"Lampiran {huruf}  {sumber:28s} -> {len(halaman)} halaman PNG")

    shutil.rmtree(TMP_DIR)
    print(f"\n{total} berkas PNG tersimpan di {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
