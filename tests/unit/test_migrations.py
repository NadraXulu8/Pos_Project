import sqlite3

from src.database.migrations import MigrationManager


def create_migration_file(path, up_sql="", down_sql=""):
    path.write_text(
        "-- +goose Up\n"
        f"{up_sql}\n\n"
        "-- +goose Down\n"
        f"{down_sql}\n",
        encoding="utf-8",
    )


def test_parse_migration_file_splits_up_and_down(tmp_path):
    db_path = tmp_path / "app.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    file_path = migrations_dir / "001_initial.sql"
    create_migration_file(file_path, up_sql="CREATE TABLE t1(id INTEGER);", down_sql="DROP TABLE t1;")

    manager = MigrationManager(str(db_path), str(migrations_dir))
    up_script, down_script = manager._parse_migration_file(str(file_path))

    assert "CREATE TABLE t1" in up_script
    assert "DROP TABLE t1" in down_script


def test_migrate_applies_pending_migrations_and_tracks_versions(tmp_path):
    db_path = tmp_path / "app.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    create_migration_file(
        migrations_dir / "001_create_system_config.sql",
        up_sql="CREATE TABLE IF NOT EXISTS system_config (id INTEGER PRIMARY KEY, key_name TEXT);",
        down_sql="DROP TABLE IF EXISTS system_config;",
    )
    create_migration_file(
        migrations_dir / "002_seed_data.sql",
        up_sql="INSERT INTO system_config (key_name) VALUES ('app_name');",
        down_sql="DELETE FROM system_config WHERE key_name='app_name';",
    )

    manager = MigrationManager(str(db_path), str(migrations_dir))
    manager.migrate()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_config'")
        assert cursor.fetchone() is not None

        cursor.execute("SELECT COUNT(*) FROM schema_version")
        assert cursor.fetchone()[0] == 2

        cursor.execute("SELECT key_name FROM system_config")
        assert cursor.fetchone()[0] == "app_name"


def test_migrate_ignores_invalid_prefix_files(tmp_path):
    db_path = tmp_path / "app.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    create_migration_file(
        migrations_dir / "abc_invalid.sql",
        up_sql="CREATE TABLE ignored_table(id INTEGER);",
        down_sql="DROP TABLE ignored_table;",
    )
    create_migration_file(
        migrations_dir / "001_valid.sql",
        up_sql="CREATE TABLE valid_table(id INTEGER);",
        down_sql="DROP TABLE valid_table;",
    )

    manager = MigrationManager(str(db_path), str(migrations_dir))
    manager.migrate()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT script_name FROM schema_version")
        assert cursor.fetchone()[0] == "001_valid.sql"


def test_rollback_runs_down_script_and_removes_last_version(tmp_path):
    db_path = tmp_path / "app.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    create_migration_file(
        migrations_dir / "001_create_system_config.sql",
        up_sql="CREATE TABLE IF NOT EXISTS system_config (id INTEGER PRIMARY KEY, key_name TEXT);",
        down_sql="DROP TABLE IF EXISTS system_config;",
    )

    manager = MigrationManager(str(db_path), str(migrations_dir))
    manager.migrate()
    manager.rollback()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_config'")
        assert cursor.fetchone() is None
