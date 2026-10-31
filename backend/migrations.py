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


async def ensure_schema():
    """Runs at application startup to synchronize database tables and columns."""
    logger.info("Running ensure_schema() migration checks...")
    async with engine.begin() as conn:
        await conn.run_sync(_inspect_and_migrate)
    logger.info("ensure_schema() migration checks complete.")
