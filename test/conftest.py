import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def set_admin_pin(repo, pin: str = "Admin#1234") -> str:
    from ism.repositories.sqlite_repo import SqliteRepository

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET pin=?, must_change_pin=0 WHERE username='admin'",
        (SqliteRepository._hash_pin(pin),),
    )
    conn.commit()
    conn.close()
    return pin