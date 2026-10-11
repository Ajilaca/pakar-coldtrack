"""Jalankan migrasi SQL polos backend/migrations/NNN_*.sql secara berurutan, masing-masing sekali.

  python -m app.db.migrate            (dari folder backend/, DATABASE_URL di env)

Setiap berkas dijalankan dalam transaksi sendiri dan dicatat di schema_migrations. Berkas yang
sudah tercatat dilewati, jadi aman dijalankan di setiap start container.
"""

import sys
from pathlib import Path

import psycopg

from app.db import dsn

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def pending(applied: set[str]) -> list[Path]:
    return [p for p in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")) if p.name not in applied]


def main() -> int:
    with psycopg.connect(dsn(), autocommit=True) as c:
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, "
                  "applied_at timestamptz NOT NULL DEFAULT now())")
        applied = {r[0] for r in c.execute("SELECT name FROM schema_migrations")}
        todo = pending(applied)
        for p in todo:
            # Satu berkas = satu kiriman query sederhana; Postgres menjalankannya sebagai SATU transaksi
            # implisit (gagal = tidak ada yang tersisa). Pernyataan yang menolak transaksi (agregat
            # kontinu Timescale) karena itu ditaruh sendirian di berkasnya.
            c.execute(p.read_text(encoding="utf-8"))
            c.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (p.name,))
            print(f"migrasi diterapkan: {p.name}")
    if not todo:
        print("tidak ada migrasi baru")
    return 0


if __name__ == "__main__":
    sys.exit(main())
