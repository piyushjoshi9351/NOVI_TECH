"""Guard against SQL that works on SQLite but not on the real MySQL.

The test suite runs against SQLite, which happily implements ``IIF()``. Oracle
MySQL 8 does not, so a conditional sum written as ``func.iif`` passed every unit
test and then took the live parent Overview endpoint down with::

    pymysql.err.OperationalError: (1305, 'FUNCTION novi_db.iif does not exist')

These tests compile the actual queries the parent projection emits using the
MySQL dialect, so a portable-SQL regression fails in CI rather than in
production.
"""

import pathlib
import re

import pytest
from sqlalchemy.dialects import mysql, sqlite

from app.services import parent_projection

APP_DIR = pathlib.Path(parent_projection.__file__).resolve().parents[1]


class _CapturingSession:
    """Minimal session stand-in that records the statement it is handed."""

    def __init__(self, row=(0, 0), rows=()):
        self._row = row
        self._rows = rows
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return self

    def one(self):
        return self._row

    def all(self):
        return self._rows


@pytest.mark.parametrize(
    "query_fn, params",
    [
        (parent_projection._roadmap_percent, (1,)),
        (parent_projection._passport_counts, (1,)),
    ],
)
def test_parent_projection_sql_is_mysql_compatible(query_fn, params):
    """No SQLite-only functions in the queries the projection builds."""
    session = _CapturingSession()
    query_fn(session, *params)
    assert session.statements, f"{query_fn.__name__} issued no query"

    for statement in session.statements:
        sql = str(
            statement.compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        assert "iif(" not in sql.lower(), (
            f"{query_fn.__name__} emits IIF(), which MySQL 8 does not implement: {sql}"
        )


def test_no_func_iif_anywhere_in_app():
    """Belt-and-braces source scan so this cannot be reintroduced silently."""
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text().splitlines(), start=1
        ):
            if re.search(r"\b(?:func|sa|sqlalchemy\.func)\s*\.\s*iif\s*\(", line):
                offenders.append(f"{path.relative_to(APP_DIR)}:{lineno}")
    assert not offenders, f"func.iif() reintroduced at {offenders}"


def test_conditional_sum_agrees_between_dialects():
    """``_sum_if`` must compile on both engines, and to the same semantics."""
    from sqlalchemy import case, column, select

    col = column("completed")
    for dialect in (sqlite.dialect(), mysql.dialect()):
        sql = str(
            select(parent_projection._sum_if(col)).compile(
                dialect=dialect, compile_kwargs={"literal_binds": True}
            )
        )
        assert "iif(" not in sql.lower()
        assert "CASE WHEN" in sql.upper(), f"unexpected SQL for {dialect.name}: {sql}"


def test_sum_if_helper_shape():
    """Guard the helper itself so it stays ``SUM(CASE ...)``, not a raw call."""
    from sqlalchemy import case, column, func, select

    col = column("completed")
    expr = parent_projection._sum_if(col)
    reference = func.sum(case((col.is_(True), 1), else_=0))

    # Behavioural check: identical SQL to the reference construction on both engines.
    for dialect in (sqlite.dialect(), mysql.dialect()):
        got = str(select(expr).compile(dialect=dialect))
        want = str(select(reference).compile(dialect=dialect))
        assert got == want, f"{dialect.name}: {got!r} != {want!r}"

    rendered = str(select(expr).compile(dialect=mysql.dialect())).upper()
    assert "SUM(CASE WHEN" in rendered
    assert "IIF(" not in rendered