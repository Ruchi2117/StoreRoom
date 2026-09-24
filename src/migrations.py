"""Additive SQLite migrations; never rebuild or erase old scan rows."""
from sqlalchemy import inspect


def initialize_schema(engine, metadata):
    from src.catalog import seed_catalog
    from src.orders import seed_customer
    additions = {
        'scans': {'source_image_path': 'TEXT', 'annotated_image_path': 'TEXT',
                  'prediction_id': 'TEXT', 'model_id': 'TEXT', 'checkpoint_sha256': 'TEXT',
                  'image_width': 'INTEGER', 'image_height': 'INTEGER'},
        'scan_items': {'product_id': 'TEXT', 'reviewed': 'BOOLEAN NOT NULL DEFAULT 1'},
    }
    with engine.begin() as connection:
        # Explicit SQLite transaction also makes the additive DDL atomic in legacy driver mode.
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        version = connection.exec_driver_sql('PRAGMA user_version').scalar()
        if version > 4:
            raise RuntimeError('Database schema is newer than this application')
        inspector = inspect(connection)
        for table, columns in additions.items():
            if table in inspector.get_table_names():
                existing = {column['name'] for column in inspector.get_columns(table)}
                for name, sql_type in columns.items():
                    if name not in existing:
                        # Identifiers/types are fixed application constants, never request data.
                        connection.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}')
        metadata.create_all(connection)
        connection.exec_driver_sql('CREATE UNIQUE INDEX IF NOT EXISTS ix_scan_prediction ON scans (prediction_id)')
        seed_catalog(connection)
        seed_customer(connection)
        connection.exec_driver_sql('PRAGMA user_version=4')
