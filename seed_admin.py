"""Create or update a moderator/admin login.

Usage:
    py seed_admin.py <username> <password> [--role admin|moderator]

Run this once to create your own login before starting the app, and again
any time you want to add another moderator or reset a password.
"""
import argparse
import getpass
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("password", nargs="?", help="omit to be prompted (safer - avoids shell history)")
    parser.add_argument("--role", choices=("admin", "moderator"), default="admin")
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")

    conn = sqlite3.connect(args.db)
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        """
        INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash, role = excluded.role
        """,
        (args.username, generate_password_hash(password), args.role),
    )
    conn.commit()
    conn.close()
    print(f"User {args.username!r} ready with role {args.role!r}.")


if __name__ == "__main__":
    main()
