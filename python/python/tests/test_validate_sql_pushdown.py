# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright The Lance Authors

"""Validation spike: Cypher → to_sql() → DataFusion + FFILanceTableProvider.

This test suite validates the dual-engine architecture's Tier-2 path:

    CypherQuery.to_sql()  →  SQL string (DataFusion dialect)
                          →  datafusion.SessionContext with FFILanceTableProvider
                          →  filter/projection pushdown into Lance row-group skipping

Tests are skipped if ``lance`` or ``datafusion`` are not installed.

HOW TO READ THESE TESTS
-----------------------
1. ``test_to_sql_*`` tests confirm the SQL generation stage in isolation.
   They use stub PyArrow tables (schema-only, 0 rows) because to_sql() only
   needs the schema for semantic analysis — it does not read data.

2. ``test_ffi_*`` tests confirm the execution stage: the generated SQL actually
   runs against real Lance files via FFILanceTableProvider and returns correct
   results.

3. ``test_explain_*`` tests capture the DataFusion EXPLAIN output. A passing
   result means the query executed without error; the printed plan should be
   inspected manually to verify that filters appear inside the scan operator
   (LanceScan / DataSourceExec) rather than as a separate FilterExec node
   above the scan.

PUSHDOWN SIGNAL
---------------
In DataFusion's physical EXPLAIN, a pushed-down filter looks like:

    DataSourceExec: ..., predicate=column > value

A non-pushed filter looks like:

    FilterExec: column > value
      DataSourceExec: ...

If you see the latter for a simple equality or range predicate, the FFI
TableProvider is not implementing the ``supports_filter_pushdown`` method, or
lance#3953 is blocking the pushdown on indexed columns.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Dict

import pyarrow as pa
import pytest

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Module-level import guards — skip the entire module if deps are absent
# ---------------------------------------------------------------------------

lance = pytest.importorskip(
    "lance",
    reason="pylance is required for FFI pushdown tests (pip install pylance)",
)
datafusion = pytest.importorskip(
    "datafusion",
    reason="datafusion-python is required for FFI pushdown tests (pip install datafusion)",
)

from lance_graph import CypherQuery, GraphConfig  # noqa: E402 — after importorskip


# ---------------------------------------------------------------------------
# Schema and sample data constants
# ---------------------------------------------------------------------------

# Financial forensics domain — deliberately small so tests run in milliseconds.
# Person nodes
PERSONS = pa.table(
    {
        "person_id": pa.array([1, 2, 3, 4, 5], type=pa.int64()),
        "name": ["Alice", "Bob", "Carol", "David", "Eve"],
        "risk_score": pa.array([0.1, 0.9, 0.3, 0.7, 0.5], type=pa.float64()),
        "country": ["US", "RU", "US", "CN", "GB"],
    }
)

# Account nodes
ACCOUNTS = pa.table(
    {
        "account_id": pa.array([101, 102, 103, 104], type=pa.int64()),
        "account_type": ["savings", "checking", "offshore", "checking"],
        "balance": pa.array([5000.0, 120000.0, 900000.0, 15000.0], type=pa.float64()),
        "currency": ["USD", "USD", "USD", "EUR"],
    }
)

# OWNS relationship (person → account)
OWNS = pa.table(
    {
        "person_id": pa.array([1, 2, 2, 3, 4], type=pa.int64()),
        "account_id": pa.array([101, 102, 103, 104, 104], type=pa.int64()),
    }
)

# TRANSFERRED_TO relationship (account → account)
TRANSFERRED_TO = pa.table(
    {
        "src_account_id": pa.array([102, 103, 101], type=pa.int64()),
        "dst_account_id": pa.array([103, 101, 104], type=pa.int64()),
        "amount": pa.array([50000.0, 200000.0, 3000.0], type=pa.float64()),
    }
)

TABLE_DATA: Dict[str, pa.Table] = {
    "Person": PERSONS,
    "Account": ACCOUNTS,
    "OWNS": OWNS,
    "TRANSFERRED_TO": TRANSFERRED_TO,
}

# GraphConfig maps node labels to their primary key columns and relationships
# to their source/target FK columns.
GRAPH_CONFIG = (
    GraphConfig.builder()
    .with_node_label("Person", "person_id")
    .with_node_label("Account", "account_id")
    .with_relationship("OWNS", "person_id", "account_id")
    .with_relationship("TRANSFERRED_TO", "src_account_id", "dst_account_id")
    .build()
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schema_stubs(tables: Dict[str, pa.Table]) -> Dict[str, pa.Table]:
    """Return empty (0-row) tables preserving the schema of each input table.

    to_sql() only needs the schema for semantic analysis, not the actual rows.
    Using stubs avoids loading full datasets just to generate SQL.
    """
    return {name: tbl.schema.empty_table() for name, tbl in tables.items()}


def _write_lance_datasets(base_dir: Path, tables: Dict[str, pa.Table]) -> Dict[str, str]:
    """Write each PyArrow table to a Lance dataset on disk.

    Returns a mapping of table name → Lance dataset path (string).
    """
    paths: Dict[str, str] = {}
    for name, table in tables.items():
        path = str(base_dir / f"{name}.lance")
        lance.write_dataset(table, path, mode="create")
        paths[name] = path
    return paths


def _build_ffi_context(lance_paths: Dict[str, str]) -> datafusion.SessionContext:
    """Create a DataFusion SessionContext with every Lance dataset registered
    through FFILanceTableProvider.

    Table names are registered in lowercase to match the lowercased identifiers
    that to_sql() emits.
    """
    ctx = datafusion.SessionContext()
    for table_name, path in lance_paths.items():
        ds = lance.dataset(path)
        try:
            provider = ds.to_table_provider()
        except AttributeError:
            pytest.skip(
                f"lance.LanceDataset.to_table_provider() not available in "
                f"lance {lance.__version__}; cannot test FFI pushdown"
            )
        try:
            ctx.register_table_provider(table_name.lower(), provider)
        except AttributeError:
            pytest.skip(
                f"datafusion.SessionContext.register_table_provider() not available "
                f"in datafusion {datafusion.__version__}; cannot test FFI pushdown"
            )
    return ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lance_dir(tmp_path_factory):
    """Module-scoped temp dir so Lance datasets are written once per test run."""
    return tmp_path_factory.mktemp("lance_datasets")


@pytest.fixture(scope="module")
def lance_paths(lance_dir):
    return _write_lance_datasets(lance_dir, TABLE_DATA)


@pytest.fixture(scope="module")
def ffi_ctx(lance_paths):
    """A DataFusion SessionContext with all Lance tables registered via FFI."""
    return _build_ffi_context(lance_paths)


@pytest.fixture
def stub_datasets():
    return _schema_stubs(TABLE_DATA)


# ---------------------------------------------------------------------------
# Stage 1 — to_sql() isolation tests (no Lance I/O, no DataFusion execution)
# ---------------------------------------------------------------------------


class TestToSqlGeneration:
    """Verify to_sql() produces structurally correct DataFusion SQL.

    These tests use stub (0-row) tables — no Lance files needed.
    """

    def test_node_scan(self, stub_datasets):
        """Simple MATCH (p:Person) RETURN → SELECT from person table."""
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.name, p.risk_score ORDER BY p.risk_score DESC"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        assert isinstance(sql, str) and sql.strip()
        upper = sql.upper()
        assert "SELECT" in upper
        assert "person" in sql.lower()
        assert "ORDER BY" in upper

    def test_node_filter(self, stub_datasets):
        """WHERE predicate must appear in generated SQL."""
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.risk_score > 0.6 RETURN p.name, p.country"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        upper = sql.upper()
        assert "WHERE" in upper
        assert "SELECT" in upper

    def test_relationship_join(self, stub_datasets):
        """One-hop MATCH (p)-[:OWNS]->(a) must produce a JOIN."""
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) RETURN p.name, a.balance"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        upper = sql.upper()
        assert "JOIN" in upper
        assert "SELECT" in upper

    def test_two_hop_join(self, stub_datasets):
        """Two-hop chain must produce two JOINs."""
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)-[:TRANSFERRED_TO]->(b:Account)
            WHERE p.risk_score > 0.5
            RETURN p.name, a.account_id, b.account_id, b.balance
            ORDER BY b.balance DESC
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        upper = sql.upper()
        assert sql.upper().count("JOIN") >= 2
        assert "WHERE" in upper
        assert "ORDER BY" in upper

    def test_aggregation_with_group_by(self, stub_datasets):
        """COUNT(*) RETURN must produce GROUP BY + COUNT in SQL."""
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            RETURN p.name, COUNT(*) AS account_count, p.risk_score
            ORDER BY account_count DESC
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        upper = sql.upper()
        assert "COUNT" in upper
        assert "GROUP BY" in upper
        assert "ORDER BY" in upper

    def test_limit(self, stub_datasets):
        """LIMIT N must appear in generated SQL."""
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.country = 'US' RETURN p.name LIMIT 3"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        assert "LIMIT" in sql.upper()

    def test_distinct(self, stub_datasets):
        """DISTINCT must translate to DISTINCT or GROUP BY."""
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) RETURN DISTINCT a.currency"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        upper = sql.upper()
        assert "DISTINCT" in upper or "GROUP BY" in upper

    def test_without_config_raises(self, stub_datasets):
        """to_sql() without a GraphConfig must raise."""
        query = CypherQuery("MATCH (p:Person) RETURN p.name")
        with pytest.raises(Exception):
            query.to_sql(stub_datasets)

    def test_sql_is_deterministic(self, stub_datasets):
        """Calling to_sql() twice on the same query must return identical SQL."""
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) WHERE a.balance > 10000 "
            "RETURN p.name, a.balance ORDER BY a.balance DESC LIMIT 5"
        ).with_config(GRAPH_CONFIG)
        sql1 = query.to_sql(stub_datasets)
        sql2 = query.to_sql(stub_datasets)
        assert sql1 == sql2


# ---------------------------------------------------------------------------
# Stage 2 — FFI execution tests (requires lance + datafusion)
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestFFIExecution:
    """Execute to_sql()-generated SQL against real Lance files via FFI.

    These tests validate that the SQL string from to_sql() can be fed
    directly into a DataFusion SessionContext that has FFILanceTableProvider
    tables registered, and that results are correct.
    """

    def test_node_scan_results(self, ffi_ctx, stub_datasets):
        """All persons are returned from a simple node scan."""
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.person_id, p.name ORDER BY p.person_id"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        assert result.num_rows == PERSONS.num_rows

    def test_filter_reduces_rows(self, ffi_ctx, stub_datasets):
        """A WHERE predicate must reduce the result set correctly."""
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.risk_score > 0.6 RETURN p.name, p.risk_score"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        expected_names = sorted(
            row["name"]
            for row in PERSONS.to_pylist()
            if row["risk_score"] > 0.6
        )
        returned_names = sorted(result.to_pydict()["name"])
        assert returned_names == expected_names

    def test_equality_filter(self, ffi_ctx, stub_datasets):
        """Equality filter (country = 'US') returns correct subset."""
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.country = 'US' RETURN p.name ORDER BY p.name"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        expected = sorted(
            r["name"] for r in PERSONS.to_pylist() if r["country"] == "US"
        )
        assert result.to_pydict()["name"] == expected

    def test_join_returns_correct_pairs(self, ffi_ctx, stub_datasets):
        """Person→Account join returns only rows present in the OWNS relationship."""
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) RETURN p.name, a.account_id "
            "ORDER BY p.name, a.account_id"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        assert result.num_rows == OWNS.num_rows

        # Every (name, account_id) pair must exist in the raw tables
        persons_map = {r["person_id"]: r["name"] for r in PERSONS.to_pylist()}
        expected_pairs = sorted(
            (persons_map[r["person_id"]], r["account_id"])
            for r in OWNS.to_pylist()
        )
        returned_pairs = sorted(
            zip(result.to_pydict()["name"], result.to_pydict()["account_id"])
        )
        assert returned_pairs == expected_pairs

    def test_join_with_filter(self, ffi_ctx, stub_datasets):
        """High-risk person → high-balance account: join + filter on both sides."""
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            WHERE p.risk_score > 0.5 AND a.balance > 100000
            RETURN p.name, a.balance
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        # Manual cross-join computation for verification
        persons_map = {r["person_id"]: r for r in PERSONS.to_pylist()}
        accounts_map = {r["account_id"]: r for r in ACCOUNTS.to_pylist()}
        expected = [
            (persons_map[o["person_id"]]["name"], accounts_map[o["account_id"]]["balance"])
            for o in OWNS.to_pylist()
            if persons_map[o["person_id"]]["risk_score"] > 0.5
            and accounts_map[o["account_id"]]["balance"] > 100000
        ]
        returned = list(
            zip(result.to_pydict()["name"], result.to_pydict()["balance"])
        )
        assert sorted(returned) == sorted(expected)

    def test_aggregation_result(self, ffi_ctx, stub_datasets):
        """COUNT(*) aggregation returns expected per-person account counts."""
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            RETURN p.name, COUNT(*) AS cnt
            ORDER BY p.name
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        result_dict = result.to_pydict()
        counts_by_name = dict(zip(result_dict["name"], result_dict["cnt"]))

        # Bob owns accounts 102 and 103 (2 accounts); David owns 104 (1, shared with Carol)
        assert counts_by_name.get("Bob") == 2

    def test_limit_caps_output(self, ffi_ctx, stub_datasets):
        """LIMIT 2 must return at most 2 rows regardless of data size."""
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.name ORDER BY p.name LIMIT 2"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        assert result.num_rows == 2


# ---------------------------------------------------------------------------
# Stage 3 — EXPLAIN / pushdown introspection
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestExplainPushdown:
    """Capture DataFusion EXPLAIN output to verify filter and projection pushdown.

    THESE TESTS DO NOT FAIL ON PLAN CONTENT — they only fail on execution errors
    or wrong result counts.  The printed plan must be inspected manually to
    confirm that WHERE predicates appear *inside* the scan operator rather than
    as a separate FilterExec node above it.

    What to look for in the printed output:
    - GOOD: "DataSourceExec: ..., predicate=..." or "LanceScan: ..., filter=..."
    - BAD:  "FilterExec: <predicate>\\n  DataSourceExec: ..." (filter not pushed)
    """

    def _explain_plan(self, ctx: datafusion.SessionContext, sql: str) -> str:
        """Return the physical plan section from EXPLAIN as a single string."""
        try:
            rows = ctx.sql(f"EXPLAIN {sql}").collect()
        except Exception:
            # Some DataFusion versions require EXPLAIN ANALYZE; try without
            return "<explain not available>"
        lines = []
        for batch in rows:
            d = batch.to_pydict()
            for plan_type, plan_text in zip(d.get("plan_type", []), d.get("plan", [])):
                lines.append(f"[{plan_type}]\n{plan_text}")
        return "\n".join(lines)

    def test_single_filter_plan(self, ffi_ctx, stub_datasets, capsys):
        """Print the plan for a simple equality filter; assert no execution error."""
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.country = 'US' RETURN p.name"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        plan = self._explain_plan(ffi_ctx, sql)
        print(f"\n[EXPLAIN single-filter]\n{plan}")

        # Execute must succeed and return correct count
        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        expected_count = sum(1 for r in PERSONS.to_pylist() if r["country"] == "US")
        assert result.num_rows == expected_count

        # Soft check: if a FilterExec appears, pushdown is NOT happening.
        # This is informational — change to hard assert once confirmed working.
        if "FilterExec" in plan:
            import warnings
            warnings.warn(
                "FilterExec detected above the scan — filter pushdown into "
                "FFILanceTableProvider is NOT active for this predicate. "
                "Check that to_table_provider() supports filter pushdown.",
                stacklevel=2,
            )

    def test_range_filter_plan(self, ffi_ctx, stub_datasets, capsys):
        """Print the plan for a range predicate; assert correct results."""
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.risk_score > 0.6 RETURN p.name, p.risk_score"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        plan = self._explain_plan(ffi_ctx, sql)
        print(f"\n[EXPLAIN range-filter]\n{plan}")

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        expected = sum(1 for r in PERSONS.to_pylist() if r["risk_score"] > 0.6)
        assert result.num_rows == expected

    def test_join_filter_plan(self, ffi_ctx, stub_datasets):
        """Print the plan for a join with filters; assert correct row count."""
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            WHERE p.risk_score > 0.5 AND a.balance > 50000
            RETURN p.name, a.balance
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        plan = self._explain_plan(ffi_ctx, sql)
        print(f"\n[EXPLAIN join-filter]\n{plan}")

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        persons_map = {r["person_id"]: r for r in PERSONS.to_pylist()}
        accounts_map = {r["account_id"]: r for r in ACCOUNTS.to_pylist()}
        expected_count = sum(
            1 for o in OWNS.to_pylist()
            if persons_map[o["person_id"]]["risk_score"] > 0.5
            and accounts_map[o["account_id"]]["balance"] > 50000
        )
        assert result.num_rows == expected_count

    def test_projection_only_requested_columns(self, ffi_ctx, stub_datasets):
        """Only columns in RETURN should appear in the result batch.

        If projection pushdown works, Lance only reads the requested columns
        from the row groups; the scan plan should list only those columns.
        """
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.name"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(stub_datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        # The result must have exactly one column
        assert result.num_columns == 1
        assert "name" in result.schema.names
