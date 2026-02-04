"""High-level helpers for working with Lance-backed knowledge graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

import pyarrow as pa
from lance_graph import CypherQuery, GraphConfig

try:  # Prefer to import for typing without raising at runtime.
    from lance_graph import GraphConfigBuilder
except ImportError:  # pragma: no cover - builder is available in normal installs.
    GraphConfigBuilder = object  # type: ignore[assignment]

from .component import KnowledgeGraphComponent
from .config import KnowledgeGraphConfig, build_graph_config_from_mapping
from .extraction import (
    DEFAULT_STRATEGY,
    BaseExtractor,
    get_extractor,
    preview_extraction,
)
from .extractors import HeuristicExtractor, LLMExtractor
from .service import LanceKnowledgeGraph, create_default_service
from .store import LanceGraphStore
from .webservice import create_app

TableMapping = Mapping[str, pa.Table]


def _ensure_table(name: str, table: pa.Table) -> pa.Table:
    if not isinstance(table, pa.Table):
        raise TypeError(
            f"Dataset '{name}' must be a pyarrow.Table (got {type(table)!r})"
        )
    return table


@dataclass(frozen=True)
class KnowledgeGraph:
    """Wraps a ``GraphConfig`` alongside the Arrow tables backing it."""

    config: GraphConfig
    _tables: Dict[str, pa.Table]

    def __init__(self, config: GraphConfig, datasets: TableMapping) -> None:
        object.__setattr__(self, "config", config)
        normalized = {
            name: _ensure_table(name, table) for name, table in datasets.items()
        }
        object.__setattr__(self, "_tables", normalized)

    def run(
        self,
        statement: str,
        *,
        datasets: Optional[TableMapping] = None,
    ):
        """Execute a Cypher statement, overriding tables when provided."""
        query = CypherQuery(statement).with_config(self.config)
        sources: Dict[str, pa.Table] = dict(self._tables)
        if datasets:
            sources.update(
                {name: _ensure_table(name, table) for name, table in datasets.items()}
            )
        return query.execute(sources)

    def tables(self) -> Dict[str, pa.Table]:
        """Return a shallow copy of the registered datasets."""
        return dict(self._tables)


class KnowledgeGraphBuilder:
    """Collects nodes, relationships, and datasets before building a graph."""

    def __init__(self) -> None:
        builder = GraphConfig.builder()
        self._builder: GraphConfigBuilder = builder  # type: ignore[annotation-unchecked]
        self._datasets: Dict[str, pa.Table] = {}

    def with_node(
        self,
        label: str,
        primary_key: str,
        table: pa.Table,
    ) -> KnowledgeGraphBuilder:
        """Register a node label and Arrow table."""
        self._builder = self._builder.with_node_label(label, primary_key)
        self._datasets[label] = _ensure_table(label, table)
        return self

    def with_relationship(
        self,
        name: str,
        source_key: str,
        target_key: str,
        table: pa.Table,
    ) -> KnowledgeGraphBuilder:
        """Register a relationship and its underlying table."""
        self._builder = self._builder.with_relationship(name, source_key, target_key)
        self._datasets[name] = _ensure_table(name, table)
        return self

    def with_dataset(self, name: str, table: pa.Table) -> KnowledgeGraphBuilder:
        """Attach arbitrary supporting datasets (e.g., reference tables)."""
        self._datasets[name] = _ensure_table(name, table)
        return self

    def with_unified_nodes(
        self,
        table: pa.Table,
        *,
        table_name: str = "nodes",
        id_field: str = "id",
        label_field: str = "node_type",
        labels: Optional[list] = None,
    ) -> KnowledgeGraphBuilder:
        """Register multiple node types from a single unified table.

        This is more efficient than splitting the table in Python and
        registering each node type separately. The filtering by node type
        is done in the Rust/DataFusion layer during query execution.

        Parameters
        ----------
        table : pa.Table
            The unified table containing all nodes with a type column.
        table_name : str
            The name to register the table under (default: "nodes").
        id_field : str
            The field serving as the node identifier (default: "id").
        label_field : str
            The field containing the node type/label (default: "node_type").
        labels : list, optional
            Specific labels to register. If None, automatically discovers
            all unique values in the label_field column.

        Returns
        -------
        KnowledgeGraphBuilder
            Self for method chaining.

        Example
        -------
        >>> # Create a unified nodes table
        >>> nodes = pa.table({
        ...     "id": [1, 2, 3, 4],
        ...     "name": ["Alice", "Bob", "Acme", "TechCo"],
        ...     "node_type": ["Person", "Person", "Company", "Company"]
        ... })
        >>> graph = (
        ...     KnowledgeGraphBuilder()
        ...     .with_unified_nodes(nodes)  # Auto-discovers Person, Company
        ...     .build()
        ... )
        """
        table = _ensure_table(table_name, table)
        self._datasets[table_name] = table

        # Auto-discover labels if not provided
        if labels is None:
            if label_field not in table.column_names:
                raise ValueError(
                    f"Label field '{label_field}' not found in table. "
                    f"Available columns: {table.column_names}"
                )
            labels = table.column(label_field).unique().to_pylist()

        # Register each label as a unified node mapping
        for label in labels:
            self._builder = self._builder.with_unified_node(
                table_name, label, id_field, label_field
            )

        return self

    def with_unified_relationships(
        self,
        table: pa.Table,
        *,
        table_name: str = "relationships",
        source_field: str = "source_id",
        target_field: str = "target_id",
        type_field: str = "relationship_type",
        types: Optional[list] = None,
    ) -> KnowledgeGraphBuilder:
        """Register multiple relationship types from a single unified table.

        This is more efficient than splitting the table in Python and
        registering each relationship type separately. The filtering by
        relationship type is done in the Rust/DataFusion layer.

        Parameters
        ----------
        table : pa.Table
            The unified table containing all relationships with a type column.
        table_name : str
            The name to register the table under (default: "relationships").
        source_field : str
            The field containing source node IDs (default: "source_id").
        target_field : str
            The field containing target node IDs (default: "target_id").
        type_field : str
            The field containing the relationship type (default: "relationship_type").
        types : list, optional
            Specific relationship types to register. If None, automatically
            discovers all unique values in the type_field column.

        Returns
        -------
        KnowledgeGraphBuilder
            Self for method chaining.

        Example
        -------
        >>> # Create a unified relationships table
        >>> rels = pa.table({
        ...     "source_id": [1, 2, 1],
        ...     "target_id": [3, 4, 2],
        ...     "relationship_type": ["WORKS_FOR", "WORKS_FOR", "KNOWS"]
        ... })
        >>> graph = (
        ...     KnowledgeGraphBuilder()
        ...     .with_unified_nodes(nodes)
        ...     .with_unified_relationships(rels)  # Auto-discovers WORKS_FOR, KNOWS
        ...     .build()
        ... )
        """
        table = _ensure_table(table_name, table)
        self._datasets[table_name] = table

        # Auto-discover types if not provided
        if types is None:
            if type_field not in table.column_names:
                raise ValueError(
                    f"Type field '{type_field}' not found in table. "
                    f"Available columns: {table.column_names}"
                )
            types = table.column(type_field).unique().to_pylist()

        # Register each type as a unified relationship mapping
        for rel_type in types:
            self._builder = self._builder.with_unified_relationship(
                table_name, rel_type, source_field, target_field, type_field
            )

        return self

    def build(self) -> KnowledgeGraph:
        """Materialize the ``KnowledgeGraph`` instance."""
        config = self._builder.build()
        return KnowledgeGraph(config, self._datasets)


__all__ = [
    "KnowledgeGraph",
    "KnowledgeGraphBuilder",
    "KnowledgeGraphConfig",
    "build_graph_config_from_mapping",
    "LanceGraphStore",
    "LanceKnowledgeGraph",
    "create_default_service",
    "KnowledgeGraphComponent",
    "create_app",
    "DEFAULT_STRATEGY",
    "BaseExtractor",
    "get_extractor",
    "preview_extraction",
    "HeuristicExtractor",
    "LLMExtractor",
]
