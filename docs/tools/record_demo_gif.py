"""Rekam GIF demo halaman Simulasi dengan Chrome tanpa kepala, lalu ubah ke GIF lewat ffmpeg.

Alur rekaman: buka /simulation, jalankan skenario "Pintu Kargo Terbuka" (KRITIS) lalu "Perjalanan Normal" (AMAN),
dengan kursor tiruan supaya klik terlihat. Browser diambil tangkapan layarnya berurutan, lalu dirangkai ffmpeg
sistem (perekam video bawaan Playwright butuh ffmpeg sendiri yang harus diunduh). Hasil: docs/images/demo.gif.

Prasyarat: stack berjalan (`docker compose up -d api frontend`), Google Chrome, ffmpeg, dan Playwright di venv
(`pip install playwright`; browser tidak perlu diunduh, skrip memakai Chrome sistem).

  python docs/tools/record_demo_gif.py                 # tulis docs/images/demo.gif
  python docs/tools/record_demo_gif.py --lebar 800     # GIF lebih kecil
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "images" / "demo.gif"

KURSOR = """
addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('kursor-demo')) return;
  const d = document.createElement('div');
  d.id = 'kursor-demo';
  d.style.cssText = 'position:fixed;z-index:99999;width:18px;height:18px;border-radius:50%;pointer-events:none;'
    + 'background:rgba(37,99,235,.55);border:2px solid #1d4ed8;left:-40px;top:-40px;transition:transform .08s;';
  document.body.appendChild(d);
  addEventListener('mousemove', e => { d.style.left = (e.clientX - 9) + 'px'; d.style.top = (e.clientY - 9) + 'px'; });
  addEventListener('mousedown', () => d.style.transform = 'scale(.7)');
  addEventListener('mouseup', () => d.style.transform = 'scale(1)');
});
"""


def cek(url, nama):
    try:
        urllib.request.urlopen(url, timeout=5)
    except (OSError, ValueError) as e:
        sys.exit(f"{nama} tidak bisa dijangkau di {url}: {e}\nNyalakan dulu: docker compose up -d api frontend")


class Perekam:
    """Ambil tangkapan layar tiap 1/fps detik selama menunggu atau menggerakkan kursor."""

    def __init__(self, page, folder, fps):
        self.page, self.folder, self.selang, self.n = page, Path(folder), 1 / fps, 0

    def bingkai(self):
        t0 = time.monotonic()
        self.page.screenshot(path=self.folder / f"f{self.n:05d}.png")
        self.n += 1
        sisa = self.selang - (time.monotonic() - t0)
        if sisa > 0:
            time.sleep(sisa)

    def tunggu(self, ms):
        akhir = time.monotonic() + ms / 1000
        while time.monotonic() < akhir:
            self.bingkai()

    def gerak(self, selector, langkah=12):
        kotak = self.page.locator(selector).first.bounding_box()
        tx, ty = kotak["x"] + kotak["width"] / 2, kotak["y"] + kotak["height"] / 2
        for i in range(1, langkah + 1):
            self.page.mouse.move(self.x + (tx - self.x) * i / langkah, self.y + (ty - self.y) * i / langkah)
            self.bingkai()
        self.x, self.y = tx, ty

    x, y = 640.0, 700.0


def main():
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:3000")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--chrome", default=shutil.which("google-chrome") or "/usr/bin/google-chrome")
    ap.add_argument("--lebar", type=int, default=960, help="lebar GIF (px)")
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--keluaran", type=Path, default=OUT)
    a = ap.parse_args()
    cek(f"{a.api}/api/v1/scenarios", "API")
    cek(a.url, "Dasbor")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg tidak ditemukan")

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        bingkai = Path(tmp) / "bingkai"
        bingkai.mkdir()
        browser = pw.chromium.launch(executable_path=a.chrome, headless=True, args=["--hide-scrollbars"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1,
                                  locale="id-ID", timezone_id="Asia/Jakarta")
        page = ctx.new_page()
        page.add_init_script(KURSOR)
        page.goto(f"{a.url}/simulation", wait_until="networkidle")
        page.wait_for_selector("select")
        rek = Perekam(page, bingkai, a.fps)
        page.mouse.move(rek.x, rek.y)
        rek.tunggu(1200)

        for skenario in ("scenario_2_door_open", "scenario_1_normal"):
            rek.gerak("select")
            rek.tunggu(250)
            page.select_option("select", skenario)
            rek.tunggu(900)
            rek.gerak("button:has-text('Analisis perjalanan')")
            rek.tunggu(350)
            page.click("button:has-text('Analisis perjalanan')")
            page.wait_for_selector("text=Faktor", timeout=15000)
            rek.tunggu(2800)
        ctx.close()
        browser.close()

        a.keluaran.parent.mkdir(parents=True, exist_ok=True)
        palet = Path(tmp) / "palet.png"
        masuk = ["-framerate", str(a.fps), "-i", str(bingkai / "f%05d.png")]
        saring = f"scale={a.lebar}:-1:flags=lanczos"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *masuk, "-vf", f"{saring},palettegen=max_colors=128",
                        str(palet)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *masuk, "-i", str(palet), "-lavfi",
                        f"{saring}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4", "-loop", "0", str(a.keluaran)],
                       check=True)
        print(f"{rek.n} bingkai")
    print(f"Tersimpan: {a.keluaran} ({a.keluaran.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
