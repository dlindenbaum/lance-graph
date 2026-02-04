"""
Example: Creating graphs from unified tables with type columns.

This example demonstrates how to create a knowledge graph from:
- A single "nodes" table with a "node_type" column distinguishing Person/Company
- A single "relationships" table with a "rel_type" column distinguishing KNOWS/WORKS_FOR

This is more efficient than splitting tables in Python because the filtering
happens in Rust/DataFusion during query execution.

Requirements:
- Build/install the Python extension first (from repo root):
  maturin develop -m python/Cargo.toml
- Python deps: pyarrow

Run:
  python examples/unified_tables.py
"""

from __future__ import annotations

import pyarrow as pa

from lance_graph import GraphConfigBuilder, CypherQuery


def make_unified_nodes() -> pa.RecordBatch:
    """Create a single table with all nodes, distinguished by node_type."""
    return pa.record_batch(
        [
            pa.array([1, 2, 3, 4, 5], type=pa.int32()),
            pa.array(["Alice", "Bob", "Acme Corp", "TechStart", "Carol"], type=pa.string()),
            pa.array(["Person", "Person", "Company", "Company", "Person"], type=pa.string()),
            # Extra properties
            pa.array([28, 34, None, None, 29], type=pa.int32()),  # age (for persons)
            pa.array([None, None, 1000, 50, None], type=pa.int32()),  # employees (for companies)
        ],
        names=["id", "name", "node_type", "age", "employees"],
    )


def make_unified_relationships() -> pa.RecordBatch:
    """Create a single table with all relationships, distinguished by rel_type."""
    return pa.record_batch(
        [
            pa.array([1, 2, 5, 1, 2], type=pa.int32()),  # source_id
            pa.array([2, 5, 1, 3, 4], type=pa.int32()),  # target_id
            pa.array(["KNOWS", "KNOWS", "KNOWS", "WORKS_FOR", "WORKS_FOR"], type=pa.string()),
            pa.array([2020, 2021, 2019, 2018, 2022], type=pa.int32()),  # since
        ],
        names=["source_id", "target_id", "rel_type", "since"],
    )


def example_low_level_api():
    """Use the low-level GraphConfigBuilder API directly."""
    print("=== Low-level API Example ===\n")

    # Configure the graph with unified tables
    config = (
        GraphConfigBuilder()
        # Both Person and Company come from the "nodes" table, filtered by node_type
        .with_unified_node("nodes", "Person", "id", "node_type")
        .with_unified_node("nodes", "Company", "id", "node_type")
        # Both KNOWS and WORKS_FOR come from "relationships" table, filtered by rel_type
        .with_unified_relationship("relationships", "KNOWS", "source_id", "target_id", "rel_type")
        .with_unified_relationship("relationships", "WORKS_FOR", "source_id", "target_id", "rel_type")
        .build()
    )

    # The datasets dict uses the SOURCE TABLE names, not the labels
    datasets = {
        "nodes": make_unified_nodes(),
        "relationships": make_unified_relationships(),
    }

    # Query 1: Find all persons over 30
    print("Query: Find all persons over age 30")
    query = CypherQuery("MATCH (n:Person) WHERE n.age > 30 RETURN n.name, n.age").with_config(config)
    result = query.execute_datafusion(datasets)
    print(f"Result: {result.to_pydict()}\n")

    # Query 2: Find all companies
    print("Query: Find all companies")
    query = CypherQuery("MATCH (c:Company) RETURN c.name, c.employees").with_config(config)
    result = query.execute_datafusion(datasets)
    print(f"Result: {result.to_pydict()}\n")

    # Query 3: Find who works for which company
    print("Query: Find who works for which company")
    query = CypherQuery(
        "MATCH (p:Person)-[:WORKS_FOR]->(c:Company) RETURN p.name, c.name"
    ).with_config(config)
    result = query.execute_datafusion(datasets)
    print(f"Result: {result.to_pydict()}\n")

    # Query 4: Find friends (KNOWS relationships)
    print("Query: Find friend relationships")
    query = CypherQuery(
        "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name"
    ).with_config(config)
    result = query.execute_datafusion(datasets)
    print(f"Result: {result.to_pydict()}\n")


def example_high_level_api():
    """Use the high-level KnowledgeGraphBuilder API with auto-discovery."""
    print("=== High-level API Example (with auto-discovery) ===\n")

    # Import the high-level builder
    from knowledge_graph import KnowledgeGraphBuilder

    # Convert batches to tables for the high-level API
    nodes_table = pa.Table.from_batches([make_unified_nodes()])
    rels_table = pa.Table.from_batches([make_unified_relationships()])

    # Build the graph - labels and relationship types are auto-discovered!
    graph = (
        KnowledgeGraphBuilder()
        .with_unified_nodes(
            nodes_table,
            table_name="nodes",
            id_field="id",
            label_field="node_type",
            # labels=["Person", "Company"]  # Optional: specify explicitly
        )
        .with_unified_relationships(
            rels_table,
            table_name="relationships",
            source_field="source_id",
            target_field="target_id",
            type_field="rel_type",
            # types=["KNOWS", "WORKS_FOR"]  # Optional: specify explicitly
        )
        .build()
    )

    # Run a query
    print("Query: Find persons and who they know")
    result = graph.run("MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name")
    print(f"Result: {result.to_pydict()}\n")


def example_lance_with_filter():
    """Use Lance datasets with predicate pushdown for filtering by case."""
    print("=== Lance Dataset Example (with predicate pushdown) ===\n")

    try:
        import lance
        import tempfile
        import os
    except ImportError:
        print("Note: This example requires 'lance' package. pip install lance")
        return

    from knowledge_graph import KnowledgeGraphBuilder

    # Create sample data with case_id for multi-tenant storage
    nodes_data = pa.table({
        "id": [1, 2, 3, 4, 5, 6, 7, 8],
        "name": ["Alice", "Bob", "Acme", "TechStart", "Carol", "Dave", "OtherCorp", "Ed"],
        "node_type": ["Person", "Person", "Company", "Company", "Person", "Person", "Company", "Person"],
        "case_id": ["case_001", "case_001", "case_001", "case_001", "case_002", "case_002", "case_002", "case_002"],
    })

    rels_data = pa.table({
        "source_id": [1, 2, 1, 5, 6, 5],
        "target_id": [2, 3, 3, 6, 7, 7],
        "rel_type": ["KNOWS", "WORKS_FOR", "WORKS_FOR", "KNOWS", "WORKS_FOR", "WORKS_FOR"],
        "case_id": ["case_001", "case_001", "case_001", "case_002", "case_002", "case_002"],
    })

    # Write to temporary Lance datasets
    with tempfile.TemporaryDirectory() as tmpdir:
        nodes_path = os.path.join(tmpdir, "nodes.lance")
        rels_path = os.path.join(tmpdir, "relationships.lance")

        lance.write_dataset(nodes_data, nodes_path)
        lance.write_dataset(rels_data, rels_path)

        # Open the datasets
        nodes_ds = lance.dataset(nodes_path)
        rels_ds = lance.dataset(rels_path)

        print(f"Total nodes in dataset: {nodes_ds.count_rows()}")
        print(f"Total relationships in dataset: {rels_ds.count_rows()}")

        # Build graph for case_001 only - filter is pushed down to Lance!
        print("\n--- Building graph for case_001 ---")
        graph = (
            KnowledgeGraphBuilder()
            .with_lance_nodes(
                nodes_ds,
                id_field="id",
                label_field="node_type",
                filter="case_id = 'case_001'"  # Predicate pushdown!
            )
            .with_lance_relationships(
                rels_ds,
                source_field="source_id",
                target_field="target_id",
                type_field="rel_type",
                filter="case_id = 'case_001'"  # Predicate pushdown!
            )
            .build()
        )

        # Only case_001 data is loaded
        print(f"Nodes loaded for case_001: {len(graph.tables()['nodes'])}")
        print(f"Relationships loaded for case_001: {len(graph.tables()['relationships'])}")

        # Query the filtered graph
        print("\nQuery: Find who works for which company in case_001")
        result = graph.run("MATCH (p:Person)-[:WORKS_FOR]->(c:Company) RETURN p.name, c.name")
        print(f"Result: {result.to_pydict()}")

        # Now build graph for case_002
        print("\n--- Building graph for case_002 ---")
        graph2 = (
            KnowledgeGraphBuilder()
            .with_lance_nodes(nodes_ds, filter="case_id = 'case_002'")
            .with_lance_relationships(rels_ds, filter="case_id = 'case_002'")
            .build()
        )

        print(f"Nodes loaded for case_002: {len(graph2.tables()['nodes'])}")

        print("\nQuery: Find who works for which company in case_002")
        result2 = graph2.run("MATCH (p:Person)-[:WORKS_FOR]->(c:Company) RETURN p.name, c.name")
        print(f"Result: {result2.to_pydict()}")


def main():
    example_low_level_api()

    try:
        example_high_level_api()
    except ImportError as e:
        print(f"Note: High-level API requires knowledge_graph package: {e}")

    try:
        example_lance_with_filter()
    except Exception as e:
        print(f"Note: Lance example error: {e}")


if __name__ == "__main__":
    main()
