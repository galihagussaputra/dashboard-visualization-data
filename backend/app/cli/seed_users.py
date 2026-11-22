import os

from app.core.db import SessionLocal
from app.core.security import bootstrap_user


def main() -> None:
    admin_password = os.environ.get("M2_ADMIN_PASSWORD")
    analyst_password = os.environ.get("M2_ANALYST_PASSWORD")
    if not admin_password or not analyst_password:
        raise SystemExit("M2_ADMIN_PASSWORD and M2_ANALYST_PASSWORD must be set")

    db = SessionLocal()
    try:
        admin = bootstrap_user(
            db,
            email="admin@localhost.invalid",
            password=admin_password,
            display_name="Local administrator",
            roles=("admin", "reviewer", "publisher", "analyst"),
        )
        analyst = bootstrap_user(
            db,
            email="analyst@localhost.invalid",
            password=analyst_password,
            display_name="Local analyst",
            roles=("analyst",),
        )
        db.commit()
        print(f"seeded users: {admin.email}, {analyst.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
