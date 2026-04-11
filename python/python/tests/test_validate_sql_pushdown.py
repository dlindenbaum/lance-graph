# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright The Lance Authors

"""Validation spike: Cypher → to_sql() → DataFusion + FFILanceTableProvider.

This test suite validates the dual-engine architecture's Tier-2 path:

    CypherQuery.to_sql()  →  SQL string (DataFusion dialect)
                          →  datafusion.SessionContext with FFILanceTableProvider
                          →  filter/projection pushdown into Lance row-group skipping

HOW TO READ THESE TESTS
-----------------------
Stage 1 — TestToSqlGeneration
    Runs to_sql() against the real (non-empty) data tables.  Only needs the
    lance-graph Rust extension (maturin develop) + pyarrow.  Lance and
    datafusion are NOT required.

    NOTE: to_sql() requires at least one row in each table — it builds an
    internal DataFusion catalog that validates the data at plan time.  Empty
    ("schema-only") tables trigger "Table has no data".  Pass the real tables.

Stage 2 — TestFFIExecution
    Writes real Lance datasets to disk, registers each through
    FFILanceTableProvider, feeds to_sql()-generated SQL into the same
    DataFusion SessionContext, and verifies row-level correctness.
    Skips automatically if lance or datafusion are not installed.

Stage 3 — TestExplainPushdown
    Captures EXPLAIN output and emits a warning if FilterExec appears above
    the scan (pushdown not active).  Only fails on wrong results or panics.

FFI API (lance 4.0.0 + datafusion 52.3.0)
------------------------------------------
    from lance.lance import FFILanceTableProvider
    ds = lance.dataset(path)
    provider = FFILanceTableProvider(ds)
    ctx.register_table("table_name", provider)   # lowercase name

PUSHDOWN SIGNAL
---------------
In DataFusion's physical EXPLAIN, a pushed-down filter looks like:

    DataSourceExec: ..., predicate=column > value

A non-pushed filter looks like:

    FilterExec: column > value
      DataSourceExec: ...
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pyarrow as pa
import pytest

# The Rust extension is always required; skip the whole module if not built.
try:
    from lance_graph import CypherQuery, GraphConfig
except ImportError:
    pytest.skip(
        "lance_graph not built — run `maturin develop` first",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Schema and sample data constants
# ---------------------------------------------------------------------------

# Financial forensics domain — small enough to run in milliseconds.
PERSONS = pa.table(
    {
        "person_id": pa.array([1, 2, 3, 4, 5], type=pa.int64()),
        "name": ["Alice", "Bob", "Carol", "David", "Eve"],
        "risk_score": pa.array([0.1, 0.9, 0.3, 0.7, 0.5], type=pa.float64()),
        "country": ["US", "RU", "US", "CN", "GB"],
    }
)

ACCOUNTS = pa.table(
    {
        "account_id": pa.array([101, 102, 103, 104], type=pa.int64()),
        "account_type": ["savings", "checking", "offshore", "checking"],
        "balance": pa.array([5000.0, 120000.0, 900000.0, 15000.0], type=pa.float64()),
        "currency": ["USD", "USD", "USD", "EUR"],
    }
)

OWNS = pa.table(
    {
        "person_id": pa.array([1, 2, 2, 3, 4], type=pa.int64()),
        "account_id": pa.array([101, 102, 103, 104, 104], type=pa.int64()),
    }
)

TRANSFERRED_TO = pa.table(
    {
        "src_account_id": pa.array([102, 103, 101], type=pa.int64()),
        "dst_account_id": pa.array([103, 101, 104], type=pa.int64()),
        "amount": pa.array([50000.0, 200000.0, 3000.0], type=pa.float64()),
    }
)

# Full (non-empty) tables for to_sql() — it requires at least 1 row per table.
TABLE_DATA: Dict[str, pa.Table] = {
    "Person": PERSONS,
    "Account": ACCOUNTS,
    "OWNS": OWNS,
    "TRANSFERRED_TO": TRANSFERRED_TO,
}

GRAPH_CONFIG = (
    GraphConfig.builder()
    .with_node_label("Person", "person_id")
    .with_node_label("Account", "account_id")
    .with_relationship("OWNS", "person_id", "account_id")
    .with_relationship("TRANSFERRED_TO", "src_account_id", "dst_account_id")
    .build()
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _lance():
    """Skip the test if pylance is not installed."""
    return pytest.importorskip(
        "lance",
        reason="pylance required for FFI tests (pip install pylance)",
    )


@pytest.fixture(scope="session")
def _datafusion():
    """Skip the test if datafusion-python is not installed."""
    return pytest.importorskip(
        "datafusion",
        reason="datafusion-python required for FFI tests (pip install datafusion)",
    )


@pytest.fixture
def datasets():
    """Full (non-empty) tables for to_sql().  Must have ≥1 row per table."""
    return dict(TABLE_DATA)


@pytest.fixture(scope="module")
def lance_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("lance_datasets")


@pytest.fixture(scope="module")
def lance_paths(lance_dir, _lance):
    """Write each table to a Lance dataset on disk; return {name: path}."""
    paths: Dict[str, str] = {}
    for name, table in TABLE_DATA.items():
        path = str(lance_dir / f"{name}.lance")
        _lance.write_dataset(table, path, mode="create")
        paths[name] = path
    return paths


@pytest.fixture(scope="module")
def ffi_ctx(lance_paths, _lance, _datafusion):
    """DataFusion SessionContext with all Lance tables registered via FFI."""
    try:
        from lance.lance import FFILanceTableProvider  # noqa: PLC0415
    except ImportError:
        pytest.skip(
            "lance.lance.FFILanceTableProvider not available in this lance version; "
            "cannot test FFI pushdown"
        )

    ctx = _datafusion.SessionContext()
    for table_name, path in lance_paths.items():
        ds = _lance.dataset(path)
        provider = FFILanceTableProvider(ds)
        # register_table is the current API (register_table_provider is deprecated)
        ctx.register_table(table_name.lower(), provider)
    return ctx


# ---------------------------------------------------------------------------
# Stage 1 — to_sql() isolation (no Lance I/O, no DataFusion)
# ---------------------------------------------------------------------------


class TestToSqlGeneration:
    """Verify to_sql() produces structurally correct DataFusion SQL.

    Requires only the lance-graph Rust extension + pyarrow — no lance or
    datafusion installation needed.

    IMPORTANT: pass non-empty tables; to_sql() errors on empty tables.
    """

    def test_node_scan(self, datasets):
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.name, p.risk_score ORDER BY p.risk_score DESC"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        assert isinstance(sql, str) and sql.strip()
        upper = sql.upper()
        assert "SELECT" in upper
        assert "person" in sql.lower()
        assert "ORDER BY" in upper

    def test_node_filter(self, datasets):
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.risk_score > 0.6 RETURN p.name, p.country"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        upper = sql.upper()
        assert "WHERE" in upper
        assert "SELECT" in upper

    def test_relationship_join(self, datasets):
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) RETURN p.name, a.balance"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        assert "JOIN" in sql.upper()

    def test_two_hop_join(self, datasets):
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)-[:TRANSFERRED_TO]->(b:Account)
            WHERE p.risk_score > 0.5
            RETURN p.name, a.account_id, b.account_id, b.balance
            ORDER BY b.balance DESC
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        upper = sql.upper()
        assert upper.count("JOIN") >= 2
        assert "WHERE" in upper
        assert "ORDER BY" in upper

    def test_aggregation_with_group_by(self, datasets):
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            RETURN p.name, COUNT(*) AS account_count, p.risk_score
            ORDER BY account_count DESC
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        upper = sql.upper()
        assert "COUNT" in upper
        assert "GROUP BY" in upper
        assert "ORDER BY" in upper

    def test_limit(self, datasets):
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.country = 'US' RETURN p.name LIMIT 3"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        assert "LIMIT" in sql.upper()

    def test_distinct(self, datasets):
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) RETURN DISTINCT a.currency"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        upper = sql.upper()
        assert "DISTINCT" in upper or "GROUP BY" in upper

    def test_without_config_raises(self, datasets):
        query = CypherQuery("MATCH (p:Person) RETURN p.name")
        with pytest.raises(Exception):
            query.to_sql(datasets)

    def test_sql_is_deterministic(self, datasets):
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) WHERE a.balance > 10000 "
            "RETURN p.name, a.balance ORDER BY a.balance DESC LIMIT 5"
        ).with_config(GRAPH_CONFIG)
        sql1 = query.to_sql(datasets)
        sql2 = query.to_sql(datasets)
        assert sql1 == sql2

    def test_print_generated_sql(self, datasets, capsys):
        """Print the SQL for each query template so it appears in -s output."""
        templates = {
            "node_scan": "MATCH (p:Person) RETURN p.name, p.risk_score",
            "filter": "MATCH (p:Person) WHERE p.risk_score > 0.6 RETURN p.name",
            "join": "MATCH (p:Person)-[:OWNS]->(a:Account) RETURN p.name, a.balance",
            "two_hop": (
                "MATCH (p:Person)-[:OWNS]->(a:Account)-[:TRANSFERRED_TO]->(b:Account) "
                "WHERE p.risk_score > 0.5 RETURN p.name, b.balance"
            ),
            "aggregation": (
                "MATCH (p:Person)-[:OWNS]->(a:Account) "
                "RETURN p.name, COUNT(*) AS cnt ORDER BY cnt DESC"
            ),
        }
        print("\n[to_sql() output for representative query templates]")
        for label, cypher in templates.items():
            sql = CypherQuery(cypher).with_config(GRAPH_CONFIG).to_sql(datasets)
            print(f"\n-- {label}\n-- Cypher: {cypher.strip()}\n{sql}")


# ---------------------------------------------------------------------------
# Stage 2 — FFI execution tests
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestFFIExecution:
    """Execute to_sql()-generated SQL against real Lance files via FFI.

    All tests skip if lance or datafusion are not installed.
    """

    def test_node_scan_results(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.person_id, p.name ORDER BY p.person_id"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        assert result.num_rows == PERSONS.num_rows

    def test_filter_reduces_rows(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.risk_score > 0.6 RETURN p.name, p.risk_score"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        # to_sql() aliases columns as "p.name", "p.risk_score" (quoted dotted names)
        d = result.to_pydict()
        col_name = next(c for c in d if "name" in c)
        expected_names = sorted(
            r["name"] for r in PERSONS.to_pylist() if r["risk_score"] > 0.6
        )
        assert sorted(d[col_name]) == expected_names

    def test_equality_filter(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.country = 'US' RETURN p.name ORDER BY p.name"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        d = result.to_pydict()
        col_name = next(c for c in d if "name" in c)
        expected = sorted(r["name"] for r in PERSONS.to_pylist() if r["country"] == "US")
        assert d[col_name] == expected

    def test_join_returns_correct_pairs(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person)-[:OWNS]->(a:Account) RETURN p.name, a.account_id "
            "ORDER BY p.name, a.account_id"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        assert result.num_rows == OWNS.num_rows

        # Columns are aliased "p.name" and "a.account_id"
        d = result.to_pydict()
        col_name = next(c for c in d if "name" in c)
        col_acct = next(c for c in d if "account_id" in c)

        persons_map = {r["person_id"]: r["name"] for r in PERSONS.to_pylist()}
        expected = sorted(
            (persons_map[r["person_id"]], r["account_id"]) for r in OWNS.to_pylist()
        )
        returned = sorted(zip(d[col_name], d[col_acct]))
        assert returned == expected

    def test_join_with_filter(self, ffi_ctx, datasets):
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            WHERE p.risk_score > 0.5 AND a.balance > 100000
            RETURN p.name, a.balance
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)

        d = result.to_pydict()
        col_name = next(c for c in d if "name" in c)
        col_balance = next(c for c in d if "balance" in c)

        persons_map = {r["person_id"]: r for r in PERSONS.to_pylist()}
        accounts_map = {r["account_id"]: r for r in ACCOUNTS.to_pylist()}
        expected = [
            (persons_map[o["person_id"]]["name"], accounts_map[o["account_id"]]["balance"])
            for o in OWNS.to_pylist()
            if persons_map[o["person_id"]]["risk_score"] > 0.5
            and accounts_map[o["account_id"]]["balance"] > 100000
        ]
        returned = list(zip(d[col_name], d[col_balance]))
        assert sorted(returned) == sorted(expected)

    def test_aggregation_result(self, ffi_ctx, datasets):
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            RETURN p.name, COUNT(*) AS cnt
            ORDER BY p.name
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        d = result.to_pydict()
        col_name = next(c for c in d if "name" in c)
        counts_by_name = dict(zip(d[col_name], d["cnt"]))
        # Bob owns accounts 102 and 103
        assert counts_by_name.get("Bob") == 2

    def test_limit_caps_output(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.name ORDER BY p.name LIMIT 2"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        assert result.num_rows == 2


# ---------------------------------------------------------------------------
# Stage 3 — EXPLAIN / pushdown introspection
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestExplainPushdown:
    """Capture DataFusion EXPLAIN output to verify filter and projection pushdown.

    Fails only on execution errors or wrong result counts.
    Warns (does not fail) if FilterExec appears above the scan — that is the
    human-readable signal that pushdown is not active.
    """

    def _explain(self, ctx, sql: str) -> str:
        try:
            rows = ctx.sql(f"EXPLAIN {sql}").collect()
        except Exception:
            return "<explain unavailable>"
        lines = []
        for batch in rows:
            d = batch.to_pydict()
            for plan_type, plan_text in zip(d.get("plan_type", []), d.get("plan", [])):
                lines.append(f"[{plan_type}]\n{plan_text}")
        return "\n".join(lines)

    def test_single_filter_plan(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.country = 'US' RETURN p.name"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)
        plan = self._explain(ffi_ctx, sql)
        print(f"\n[EXPLAIN single-filter]\n{plan}")

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        expected_count = sum(1 for r in PERSONS.to_pylist() if r["country"] == "US")
        assert result.num_rows == expected_count

        if "FilterExec" in plan:
            import warnings
            warnings.warn(
                "FilterExec detected above the scan — filter pushdown into "
                "FFILanceTableProvider is NOT active for this predicate.",
                stacklevel=2,
            )

    def test_range_filter_plan(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person) WHERE p.risk_score > 0.6 RETURN p.name, p.risk_score"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)
        plan = self._explain(ffi_ctx, sql)
        print(f"\n[EXPLAIN range-filter]\n{plan}")

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        expected = sum(1 for r in PERSONS.to_pylist() if r["risk_score"] > 0.6)
        assert result.num_rows == expected

    def test_join_filter_plan(self, ffi_ctx, datasets):
        query = CypherQuery(
            """
            MATCH (p:Person)-[:OWNS]->(a:Account)
            WHERE p.risk_score > 0.5 AND a.balance > 50000
            RETURN p.name, a.balance
            """
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)
        plan = self._explain(ffi_ctx, sql)
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

    def test_projection_only_requested_columns(self, ffi_ctx, datasets):
        query = CypherQuery(
            "MATCH (p:Person) RETURN p.name"
        ).with_config(GRAPH_CONFIG)
        sql = query.to_sql(datasets)

        batches = ffi_ctx.sql(sql).collect()
        result = pa.concat_batches(batches)
        assert result.num_columns == 1
        # to_sql() aliases the column as "p.name" (the Cypher variable + property)
        assert any("name" in col for col in result.schema.names)
