from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AuditFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditFailure(message)


def main() -> None:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    preflight_text = (ROOT / "runtime_preflight.py").read_text(encoding="utf-8")
    migration_text = (ROOT / "db_migrations.py").read_text(encoding="utf-8")
    background_text = (ROOT / "cogs" / "background.py").read_text(encoding="utf-8")

    require("Intents.all()" not in app_text, "Intents.all() must not return")
    require(
        'EXPECTED_PRODUCTION_DB = "/data/akane_v26.db"' in preflight_text,
        "production DB identity drifted",
    )
    require(
        "never deletes or recreates the database" in migration_text,
        "migration non-destructive contract is missing",
    )
    require(
        "list_due_reminders" in background_text
        and "delete_reminder(reminder_id)" in background_text,
        "reminder delivery acknowledgement contract drifted",
    )

    destructive_migration_tokens = (
        "DROP TABLE users",
        "DELETE FROM users",
        "DROP TABLE weekly_xp",
        "DELETE FROM weekly_xp",
        "DROP TABLE user_stats",
        "DELETE FROM user_stats",
    )
    for token in destructive_migration_tokens:
        require(token not in migration_text, f"destructive migration token found: {token}")

    print("PRE_DOGFOOD_STATIC_AUDIT_PASS")


if __name__ == "__main__":
    main()
