# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright The Lance Authors

"""Reproducer for lance#3953: FFILanceTableProvider panics on BTREE-indexed column.

Issue summary (June 2025)
-------------------------
When a Lance dataset has a scalar BTREE index on a column and a DataFusion
filter is pushed down to that column through FFILanceTableProvider, the
process panics (SIGABRT / RuntimeError from a Rust unwrap).

Reference: https://github.com/lancedb/lance/issues/3953

HOW TO READ THESE TESTS
-----------------------
Every test in ``TestBtreeIndexWithFFI`` first creates a Lance dataset on disk,
builds a BTREE scalar index on a filter column, then registers it through
FFILanceTableProvider and executes a filter query.

Outcomes:

* PASS  → the bug is NOT present in this lance version.  Safe to use BTREE
          indices on FFI-pushed-down columns.

* FAIL (RuntimeError / panic) → the bug IS present.  Do one of:
      (a) Remove BTREE indices from columns used in FFI filter paths.
      (b) Disable filter pushdown for indexed columns at the provider level.
      (c) Comment on lance#3953 with your repro version matrix and escalate.

* SKIP  → lance or datafusion is not installed, or to_table_provider() /
          register_table_provider() APIs differ in this version.

VERSION MATRIX (fill in as you run)
-------------------------------------
| lance  | datafusion | BTREE equality | BTREE range | BTREE IN | status |
|--------|------------|----------------|-------------|----------|--------|
| 1.0.2  | ??         |                |             |          | TBD    |

RUN WITH
--------
    pytest python/python/tests/test_lance_ffi_btree_repro.py -v -s

The ``-s`` flag shows print output, which includes the lance and datafusion
versions so they appear in CI logs.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Dict

import pyarrow as pa
import pytest

# ---------------------------------------------------------------------------
# Module-level import guards
# ---------------------------------------------------------------------------

lance = pytest.importorskip(
    "lance",
    reason="pylance required (pip install pylance)",
)
datafusion = pytest.importorskip(
    "datafusion",
    reason="datafusion-python required (pip install datafusion)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity_table(n: int = 100) -> pa.Table:
    """Create a small synthetic entity table suitable for scalar indexing."""
    import random

    rng = random.Random(42)
    entity_ids = list(range(1, n + 1))
    names = [f"entity_{i}" for i in entity_ids]
    scores = [round(rng.uniform(0.0, 1.0), 4) for _ in range(n)]
    categories = [rng.choice(["A", "B", "C", "D"]) for _ in range(n)]
    return pa.table(
        {
            "entity_id": pa.array(entity_ids, type=pa.int64()),
            "name": pa.array(names, type=pa.string()),        # pa.string() = utf8
            "score": pa.array(scores, type=pa.float64()),
            "category": pa.array(categories, type=pa.string()),  # not large_string
        }
    )


def _write_and_index(
    tmp_path: Path,
    table: pa.Table,
    index_column: str,
    dataset_name: str = "entities",
) -> "lance.LanceDataset":
    """Write a Lance dataset and build a BTREE index on ``index_column``.

    Returns the opened dataset so the caller can immediately use it.
    """
    path = str(tmp_path / f"{dataset_name}.lance")
    ds = lance.write_dataset(table, path, mode="create")
    ds.create_scalar_index(index_column, index_type="BTREE")
    # Re-open so the index is visible
    return lance.dataset(path)


def _register_ffi(
    ctx: "datafusion.SessionContext",
    ds: "lance.LanceDataset",
    table_name: str,
) -> None:
    """Register *ds* into *ctx* via FFILanceTableProvider.

    API (lance 4.0.0 + datafusion 52.3.0):
        from lance.lance import FFILanceTableProvider
        provider = FFILanceTableProvider(ds)
        ctx.register_table(table_name, provider)

    Skips the test if the required APIs are not available in the installed
    versions of lance / datafusion.
    """
    try:
        from lance.lance import FFILanceTableProvider  # noqa: PLC0415
    except ImportError:
        pytest.skip(
            f"lance {lance.__version__}: lance.lance.FFILanceTableProvider not found. "
            "Cannot test FFI pushdown."
        )
    provider = FFILanceTableProvider(ds)
    try:
        ctx.register_table(table_name, provider)
    except AttributeError:
        pytest.skip(
            f"datafusion {datafusion.__version__}: "
            "SessionContext.register_table() missing. "
            "Cannot test FFI pushdown."
        )


def _run_query(ctx: "datafusion.SessionContext", sql: str) -> pa.Table:
    """Execute *sql* and return results as a single PyArrow table.

    Any RuntimeError is re-raised so callers can distinguish panics from
    ordinary query failures.
    """
    batches = ctx.sql(sql).collect()
    return pa.concat_batches(batches)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def entity_table() -> pa.Table:
    return _make_entity_table(n=100)


@pytest.fixture
def no_index_ctx(tmp_path, entity_table):
    """Baseline: Lance dataset with NO scalar index, registered via FFI."""
    path = str(tmp_path / "entities_no_index.lance")
    lance.write_dataset(entity_table, path, mode="create")
    ds = lance.dataset(path)

    ctx = datafusion.SessionContext()
    _register_ffi(ctx, ds, "entities")
    return ctx, entity_table


@pytest.fixture
def btree_int_ctx(tmp_path, entity_table):
    """Lance dataset with BTREE index on integer column ``entity_id``."""
    ds = _write_and_index(tmp_path, entity_table, "entity_id", "entities_btree_int")
    ctx = datafusion.SessionContext()
    _register_ffi(ctx, ds, "entities")
    return ctx, entity_table


@pytest.fixture
def btree_float_ctx(tmp_path, entity_table):
    """Lance dataset with BTREE index on float column ``score``."""
    ds = _write_and_index(tmp_path, entity_table, "score", "entities_btree_float")
    ctx = datafusion.SessionContext()
    _register_ffi(ctx, ds, "entities")
    return ctx, entity_table


@pytest.fixture
def btree_string_ctx(tmp_path, entity_table):
    """Lance dataset with BTREE index on string column ``category``."""
    ds = _write_and_index(tmp_path, entity_table, "category", "entities_btree_str")
    ctx = datafusion.SessionContext()
    _register_ffi(ctx, ds, "entities")
    return ctx, entity_table


# ---------------------------------------------------------------------------
# Baseline — no index (sanity check, must always pass)
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestNoIndexBaseline:
    """Ensure basic filter queries work without any scalar index.

    If these tests fail, the environment setup is broken — nothing to do
    with lance#3953.
    """

    def test_full_scan(self, no_index_ctx):
        ctx, table = no_index_ctx
        result = _run_query(ctx, "SELECT entity_id, name FROM entities ORDER BY entity_id")
        assert result.num_rows == table.num_rows

    def test_equality_filter(self, no_index_ctx):
        ctx, table = no_index_ctx
        result = _run_query(ctx, "SELECT entity_id FROM entities WHERE entity_id = 42")
        assert result.num_rows == 1
        assert result.to_pydict()["entity_id"] == [42]

    def test_range_filter(self, no_index_ctx):
        ctx, table = no_index_ctx
        result = _run_query(ctx, "SELECT entity_id FROM entities WHERE score > 0.8")
        expected = [
            r["entity_id"] for r in table.to_pylist() if r["score"] > 0.8
        ]
        assert result.num_rows == len(expected)

    def test_string_equality_filter(self, no_index_ctx):
        ctx, table = no_index_ctx
        result = _run_query(ctx, "SELECT entity_id FROM entities WHERE category = 'A'")
        expected = [r["entity_id"] for r in table.to_pylist() if r["category"] == "A"]
        assert result.num_rows == len(expected)


# ---------------------------------------------------------------------------
# lance#3953 reproducer — BTREE on integer column
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestBtreeIntIndex:
    """BTREE index on integer column ``entity_id``.

    These are the core reproducer tests.  A panic manifests as a RuntimeError
    raised by the PyO3 FFI boundary.
    """

    def test_equality_filter_no_panic(self, btree_int_ctx):
        """Equality filter on BTREE-indexed integer column must not panic.

        Failure mode for lance#3953: RuntimeError (Rust unwrap panic).
        """
        ctx, table = btree_int_ctx
        target_id = 50  # exists in the dataset

        try:
            result = _run_query(
                ctx, f"SELECT entity_id, name FROM entities WHERE entity_id = {target_id}"
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED on lance {lance.__version__}: "
                f"FFILanceTableProvider panicked on equality filter over "
                f"BTREE-indexed integer column.\n"
                f"Error: {exc}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )

        # Correctness check if no panic
        assert result.num_rows == 1
        assert result.to_pydict()["entity_id"] == [target_id]

    def test_range_filter_no_panic(self, btree_int_ctx):
        """Range filter on BTREE-indexed integer column must not panic."""
        ctx, table = btree_int_ctx

        try:
            result = _run_query(
                ctx, "SELECT entity_id FROM entities WHERE entity_id BETWEEN 10 AND 20"
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: range filter on BTREE integer column panicked. "
                f"lance={lance.__version__}\nError: {exc}"
            )

        expected_count = sum(1 for r in table.to_pylist() if 10 <= r["entity_id"] <= 20)
        assert result.num_rows == expected_count

    def test_in_list_filter_no_panic(self, btree_int_ctx):
        """IN list filter on BTREE-indexed integer column must not panic."""
        ctx, table = btree_int_ctx
        targets = (10, 20, 30, 40, 50)

        try:
            result = _run_query(
                ctx,
                f"SELECT entity_id FROM entities WHERE entity_id IN {targets}",
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: IN-list filter on BTREE integer column panicked. "
                f"lance={lance.__version__}\nError: {exc}"
            )

        assert result.num_rows == len(targets)

    def test_compound_filter_no_panic(self, btree_int_ctx):
        """Compound filter (BTREE-indexed AND non-indexed column) must not panic."""
        ctx, table = btree_int_ctx

        try:
            result = _run_query(
                ctx,
                "SELECT entity_id, score FROM entities "
                "WHERE entity_id > 80 AND score > 0.5",
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: compound filter on BTREE integer column "
                f"panicked. lance={lance.__version__}\nError: {exc}"
            )

        expected = [
            r for r in table.to_pylist()
            if r["entity_id"] > 80 and r["score"] > 0.5
        ]
        assert result.num_rows == len(expected)


# ---------------------------------------------------------------------------
# lance#3953 reproducer — BTREE on float column
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestBtreeFloatIndex:
    """BTREE index on float column ``score``."""

    def test_equality_filter_no_panic(self, btree_float_ctx):
        """Exact-value equality filter on BTREE-indexed float must not panic."""
        ctx, table = btree_float_ctx
        # Pick a value known to exist
        target_score = table.to_pydict()["score"][0]

        try:
            result = _run_query(
                ctx, f"SELECT entity_id FROM entities WHERE score = {target_score}"
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: equality filter on BTREE float column panicked. "
                f"lance={lance.__version__}\nError: {exc}"
            )

        expected = sum(1 for r in table.to_pylist() if r["score"] == target_score)
        assert result.num_rows == expected

    def test_range_filter_no_panic(self, btree_float_ctx):
        """Range filter on BTREE-indexed float column must not panic."""
        ctx, table = btree_float_ctx

        try:
            result = _run_query(
                ctx, "SELECT entity_id, score FROM entities WHERE score > 0.7"
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: range filter on BTREE float column panicked. "
                f"lance={lance.__version__}\nError: {exc}"
            )

        expected = sum(1 for r in table.to_pylist() if r["score"] > 0.7)
        assert result.num_rows == expected


# ---------------------------------------------------------------------------
# lance#3953 reproducer — BTREE on string column
# ---------------------------------------------------------------------------


@pytest.mark.requires_lance
class TestBtreeStringIndex:
    """BTREE index on string column ``category``."""

    def test_equality_filter_no_panic(self, btree_string_ctx):
        """String equality filter on BTREE-indexed column must not panic.

        This is the most likely trigger for lance#3953 because string
        comparison requires a different code path in the BTREE index scanner.
        """
        ctx, table = btree_string_ctx

        try:
            result = _run_query(
                ctx, "SELECT entity_id, category FROM entities WHERE category = 'A'"
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: equality filter on BTREE string column "
                f"panicked. lance={lance.__version__}\nError: {exc}"
            )

        expected = sum(1 for r in table.to_pylist() if r["category"] == "A")
        assert result.num_rows == expected

    def test_in_list_filter_no_panic(self, btree_string_ctx):
        """IN list filter on BTREE-indexed string column must not panic."""
        ctx, table = btree_string_ctx

        try:
            result = _run_query(
                ctx, "SELECT entity_id FROM entities WHERE category IN ('A', 'B')"
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: IN-list filter on BTREE string column "
                f"panicked. lance={lance.__version__}\nError: {exc}"
            )

        expected = sum(1 for r in table.to_pylist() if r["category"] in ("A", "B"))
        assert result.num_rows == expected

    def test_like_filter_no_panic(self, btree_string_ctx):
        """LIKE filter on BTREE-indexed string column must not panic."""
        ctx, table = btree_string_ctx

        try:
            result = _run_query(
                ctx, "SELECT entity_id FROM entities WHERE category LIKE 'A%'"
            )
        except RuntimeError as exc:
            pytest.fail(
                f"lance#3953 REPRODUCED: LIKE filter on BTREE string column panicked. "
                f"lance={lance.__version__}\nError: {exc}"
            )

        # LIKE 'A%' should match only 'A' in our single-char category data
        expected = sum(1 for r in table.to_pylist() if r["category"].startswith("A"))
        assert result.num_rows == expected


# ---------------------------------------------------------------------------
# Version report (always runs; informational)
# ---------------------------------------------------------------------------


def test_version_report(capsys):
    """Print the version matrix row so CI logs always show what was tested."""
    lance_version = getattr(lance, "__version__", "unknown")
    datafusion_version = getattr(datafusion, "__version__", "unknown")
    print(
        f"\n[lance#3953 version matrix]\n"
        f"  lance      = {lance_version}\n"
        f"  datafusion = {datafusion_version}\n"
        f"  To update the table in this file's module docstring, run:\n"
        f"    pytest {__file__} -v -s | grep '\\[lance#3953'"
    )
