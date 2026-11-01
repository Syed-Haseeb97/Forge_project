"""
Database schema migrations helper.
Inspects existing schema and applies additive changes (e.g. ADD COLUMN) without data loss.
Compatible with SQLite and PostgreSQL (Supabase).
"""
import logging
from sqlalchemy import inspect, text
from database import engine, Base
import models  # Ensure all model tables are registered in Base.metadata

logger = logging.getLogger("janaawaz.migrations")


def _inspect_and_migrate(connection):
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    dialect_name = connection.dialect.name

    # 1. Create any missing tables defined in models
    Base.metadata.create_all(connection)

    # 2. Inspect each model table for missing columns
    for table_name, table in Base.metadata.tables.items():
        if table_name in existing_tables:
            existing_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name not in existing_columns:
                    col_type = column.type.compile(connection.dialect)
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"
                    logger.info(f"Adding missing column to {table_name}: {sql}")
                    try:
                        connection.execute(text(sql))
                    except Exception as e:
                        logger.warning(f"Failed to add column {column.name} to {table_name}: {e}")

    # 3. Handle nullable aadhaar_last4 if on Postgres
    if "citizens" in existing_tables:
        try:
            if dialect_name == "postgresql":
                connection.execute(text("ALTER TABLE citizens ALTER COLUMN aadhaar_last4 DROP NOT NULL;"))
                logger.info("Ensured citizens.aadhaar_last4 is nullable on PostgreSQL.")
        except Exception as e:
            logger.debug(f"Aadhaar nullable adjustment note: {e}")

    # 4. Backfill sequential docket numbers (JA-2026-00001) for existing reports ordered by created_at
    if "reports" in existing_tables:
        try:
            reports_rows = connection.execute(
                text("SELECT id, docket_no FROM reports ORDER BY created_at ASC")
            ).fetchall()
            max_num = 0
            for r in reports_rows:
                if r[1] and r[1].startswith("JA-2026-"):
                    try:
                        n = int(r[1].split("-")[-1])
                        if n > max_num:
                            max_num = n
                    except ValueError:
                        pass

            counter = max_num
            for r in reports_rows:
                if not r[1]:
                    counter += 1
                    docket_val = f"JA-2026-{counter:05d}"
                    connection.execute(
                        text("UPDATE reports SET docket_no = :docket WHERE id = :id"),
                        {"docket": docket_val, "id": r[0]},
                    )
                    logger.info(f"Backfilled report {r[0]} with docket_no={docket_val}")
        except Exception as e:
            logger.warning(f"Error backfilling docket numbers: {e}")

    # 5. Backfill missing tracking_token for existing reports
    if "reports" in existing_tables:
        try:
            from agent.tokens import generate_tracking_token
            # Check if tracking_token column exists in inspector
            rep_cols = {col["name"] for col in inspector.get_columns("reports")}
            if "tracking_token" in rep_cols:
                untokened = connection.execute(
                    text("SELECT id FROM reports WHERE tracking_token IS NULL")
                ).fetchall()
                for row in untokened:
                    tok = generate_tracking_token()
                    connection.execute(
                        text("UPDATE reports SET tracking_token = :tok WHERE id = :id"),
                        {"tok": tok, "id": row[0]},
                    )
                    logger.info(f"Backfilled report {row[0]} with tracking_token={tok}")
        except Exception as e:
            logger.warning(f"Error backfilling tracking tokens: {e}")


async def ensure_schema():
    """Runs at application startup to synchronize database tables and columns."""
    logger.info("Running ensure_schema() migration checks...")
    async with engine.begin() as conn:
        await conn.run_sync(_inspect_and_migrate)
    logger.info("ensure_schema() migration checks complete.")
