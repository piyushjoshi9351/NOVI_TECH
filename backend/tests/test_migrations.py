"""Tests for the SQL migration runner's statement splitter.

`_statements` looks like a two-line helper and is exactly the kind of function
that gets "simplified" without anyone checking the 5 real migration files it has
to parse. These tests pin the two properties that matter: comments are removed,
and nothing survives to corrupt the statement that follows.
"""

from pathlib import Path

from app.db.run_migrations import MIGRATIONS_DIR, _statements


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "m.sql"
    p.write_text(body, encoding="utf-8")
    return p


def test_splits_on_semicolons(tmp_path):
    p = _write(tmp_path, "CREATE TABLE a (id INT);\nCREATE TABLE b (id INT);\n")
    assert _statements(p) == ["CREATE TABLE a (id INT)", "CREATE TABLE b (id INT)"]


def test_strips_full_line_comments(tmp_path):
    p = _write(tmp_path, "-- a comment\nSELECT 1;\n-- another\nSELECT 2;\n")
    assert _statements(p) == ["SELECT 1", "SELECT 2"]


def test_ignores_blank_lines_and_normalises_whitespace(tmp_path):
    p = _write(tmp_path, "\n\nSELECT\n   1  ;\n\n")
    assert _statements(p) == ["SELECT 1"]


def test_multiline_comment_containing_a_semicolon_does_not_corrupt_next_statement(
    tmp_path,
):
    """Regression: comments must be stripped BEFORE splitting on ';'.

    Splitting first cuts the comment in half and glues the surviving fragment
    onto the next statement, so `SET @ddl := (` becomes
    `... and strips "--" lines, SET @ddl := (` -- which MySQL rejects at apply
    time, long after the code looks fine.
    """
    p = _write(
        tmp_path,
        "-- NOTE: this runner splits on ';' and strips '--' lines.\n"
        "-- so never use a semicolon in a literal.\n"
        "SET @ddl := (SELECT 1);\n"
        "PREPARE stmt FROM @ddl;\n",
    )
    assert _statements(p) == [
        "SET @ddl := (SELECT 1)",
        "PREPARE stmt FROM @ddl",
    ]


def test_trailing_statement_without_semicolon_is_kept(tmp_path):
    p = _write(tmp_path, "SELECT 1;\nSELECT 2")
    assert _statements(p) == ["SELECT 1", "SELECT 2"]


def test_comment_only_file_yields_no_statements(tmp_path):
    p = _write(tmp_path, "-- nothing to do here\n-- really\n")
    assert _statements(p) == []


def test_every_real_migration_parses(tmp_path):
    """Each shipped migration must yield only plausible SQL, not comment debris."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    assert files, f"no migrations found in {MIGRATIONS_DIR}"

    for f in files:
        for stmt in _statements(f):
            first = stmt.split()[0].upper()
            assert first in {
                "SET", "PREPARE", "EXECUTE", "DEALLOCATE", "CREATE",
                "ALTER", "DROP", "INSERT", "UPDATE", "DELETE", "SELECT",
            }, f"{f.name}: unexpected statement start {first!r}: {stmt[:80]!r}"


def test_parent_insight_cache_migration_is_idempotent_by_construction():
    """0005 must no-op when ORM create_all already made the table."""
    f = MIGRATIONS_DIR / "0005_parent_insight_cache.sql"
    stmts = _statements(f)
    joined = " ".join(stmts)
    assert "CREATE TABLE IF NOT EXISTS" in joined
    assert "information_schema.tables" in joined
    # The PREPARE dance is what makes the IF NOT EXISTS meaningful, so it must
    # survive the split intact.
    assert any(s.upper().startswith("PREPARE") for s in stmts)
    assert any(s.upper().startswith("DEALLOCATE") for s in stmts)