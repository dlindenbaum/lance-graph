#!/usr/bin/env python3
"""Example of using DuckDB tools with the Graph Review Agent."""

import duckdb
from pathlib import Path

# Create example DuckDB database with CDR data
def create_example_duckdb():
    """Create an example DuckDB database with sample CDR data."""
    db_path = Path("./cdr_data.duckdb")

    # Connect to DuckDB
    con = duckdb.connect(str(db_path))

    # Create call_records table
    con.execute("""
        CREATE OR REPLACE TABLE call_records (
            call_id INTEGER PRIMARY KEY,
            from_number VARCHAR,
            to_number VARCHAR,
            call_timestamp TIMESTAMP,
            duration_seconds INTEGER,
            call_type VARCHAR,
            tower_id VARCHAR,
            location VARCHAR
        )
    """)

    # Insert sample data
    con.execute("""
        INSERT INTO call_records VALUES
            (1, '555-0199', '555-1024', '2024-01-15 09:23:00', 245, 'voice', 'TOWER-001', 'Arlington, VA'),
            (2, '555-0199', '555-1024', '2024-01-16 09:18:00', 312, 'voice', 'TOWER-001', 'Arlington, VA'),
            (3, '555-0199', '555-2048', '2024-01-15 14:30:00', 156, 'voice', 'TOWER-002', 'McLean, VA'),
            (4, '555-1024', '555-3072', '2024-01-17 11:45:00', 89, 'sms', 'TOWER-001', 'Arlington, VA'),
            (5, '555-0199', '555-1024', '2024-01-18 09:20:00', 290, 'voice', 'TOWER-001', 'Arlington, VA'),
            (6, '555-2048', '555-4096', '2024-01-16 16:00:00', 445, 'voice', 'TOWER-003', 'Fairfax, VA'),
            (7, '555-0199', '555-5120', '2024-01-19 10:30:00', 67, 'voice', 'TOWER-001', 'Arlington, VA'),
            (8, '555-1024', '555-0199', '2024-01-20 15:15:00', 201, 'voice', 'TOWER-001', 'Arlington, VA')
    """)

    # Create subscribers table
    con.execute("""
        CREATE OR REPLACE TABLE subscribers (
            phone_number VARCHAR PRIMARY KEY,
            subscriber_name VARCHAR,
            carrier VARCHAR,
            plan_type VARCHAR,
            registration_date DATE,
            address VARCHAR
        )
    """)

    con.execute("""
        INSERT INTO subscribers VALUES
            ('555-0199', 'John Doe', 'Verizon', 'Unlimited', '2020-01-15', '123 Main St, Arlington, VA'),
            ('555-1024', 'Sarah Chen', 'Verizon', 'Premium', '2019-05-20', '1842 Oak St, Arlington, VA'),
            ('555-2048', 'Mike Johnson', 'AT&T', 'Basic', '2021-03-10', '456 Elm Ave, McLean, VA'),
            ('555-3072', 'Alice Brown', 'T-Mobile', 'Unlimited', '2018-11-05', '789 Pine Rd, Fairfax, VA'),
            ('555-4096', 'Bob Wilson', 'Verizon', 'Premium', '2015-07-22', '321 Maple Dr, Alexandria, VA')
    """)

    # Create tower_locations table
    con.execute("""
        CREATE OR REPLACE TABLE tower_locations (
            tower_id VARCHAR PRIMARY KEY,
            latitude DOUBLE,
            longitude DOUBLE,
            coverage_area VARCHAR,
            tower_type VARCHAR
        )
    """)

    con.execute("""
        INSERT INTO tower_locations VALUES
            ('TOWER-001', 38.8816, -77.1045, 'Arlington Downtown', '5G'),
            ('TOWER-002', 38.9338, -77.1773, 'McLean Center', '4G'),
            ('TOWER-003', 38.8462, -77.3064, 'Fairfax', '5G')
    """)

    con.close()
    print(f"✅ Created example DuckDB database: {db_path}")
    print(f"   - call_records: 8 rows")
    print(f"   - subscribers: 5 rows")
    print(f"   - tower_locations: 3 rows")

    return db_path


# Demonstrate DuckDB tools usage
def demonstrate_tools():
    """Demonstrate how to use DuckDB tools."""
    from knowledge_graph.agent.duckdb_tools import (
        DuckDBQueryTool,
        DataAnalysisTool,
        NodeProposalGenerator,
    )

    # Create example database
    db_path = create_example_duckdb()

    print("\n" + "="*60)
    print("DUCKDB TOOLS DEMONSTRATION")
    print("="*60)

    # Initialize tools
    with DuckDBQueryTool(db_path, read_only=True) as db_tool:
        analysis_tool = DataAnalysisTool(db_tool)
        proposal_gen = NodeProposalGenerator(analysis_tool)

        # 1. List tables
        print("\n📋 Available Tables:")
        tables = db_tool.get_tables()
        for table in tables:
            print(f"   - {table}")

        # 2. Get schema
        print("\n📐 Schema for 'call_records':")
        schema = db_tool.get_schema("call_records")
        for col in schema:
            print(f"   - {col['column_name']}: {col['data_type']}")

        # 3. Execute SQL query
        print("\n🔍 SQL Query - High frequency callers:")
        result = db_tool.execute_query("""
            SELECT from_number, COUNT(*) as call_count
            FROM call_records
            GROUP BY from_number
            ORDER BY call_count DESC
            LIMIT 3
        """)
        for row in result:
            print(f"   {row['from_number']}: {row['call_count']} calls")

        # 4. Search across tables
        print("\n🔎 Search for 'Arlington' across all tables:")
        search_results = db_tool.search_across_tables("Arlington")
        print(f"   Found {len(search_results)} matches")
        for i, row in enumerate(search_results[:3], 1):
            print(f"   {i}. Table: {row['_source_table']}")

        # 5. Find frequent patterns
        print("\n📊 Frequent patterns in call_records.from_number:")
        patterns = analysis_tool.find_frequent_patterns("call_records", "from_number", min_frequency=2)
        for row in patterns[:3]:
            print(f"   {row['value']}: {row['frequency']} occurrences")

        # 6. Find correlations
        print("\n🔗 Correlations between from_number and to_number:")
        correlations = analysis_tool.find_correlations("call_records", "from_number", "to_number")
        for row in correlations[:3]:
            print(f"   {row['from_number']} ↔ {row['to_number']}: {row['co_occurrence_count']} times")

        # 7. Temporal analysis
        print("\n📅 Temporal analysis of calls:")
        temporal = analysis_tool.temporal_analysis("call_records", "call_timestamp", "day")
        for row in temporal[:3]:
            print(f"   {row['time_period']}: {row['event_count']} calls")

        # 8. Propose nodes from entities
        print("\n➕ Propose Phone nodes from subscribers:")
        node_proposals = proposal_gen.propose_nodes_from_entities(
            table="subscribers",
            entity_column="phone_number",
            entity_type="Phone",
            property_columns=["subscriber_name", "carrier", "plan_type"],
            min_confidence=70
        )
        for proposal in node_proposals[:3]:
            print(f"   {proposal['label']}: {proposal['properties']} (confidence: {proposal['confidence']}%)")

        # 9. Propose relationships from correlation
        print("\n🔗 Propose CONTACTED relationships from call_records:")
        rel_proposals = proposal_gen.propose_relationships_from_correlation(
            table="call_records",
            from_column="from_number",
            to_column="to_number",
            relationship_type="CONTACTED",
            min_co_occurrence=2
        )
        for proposal in rel_proposals[:3]:
            print(f"   {proposal['from']} → {proposal['to']}: {proposal['properties']['co_occurrence_count']} calls")

        # 10. Propose nodes from patterns
        print("\n🎯 Propose Location nodes from frequent patterns:")
        location_proposals = proposal_gen.propose_nodes_from_patterns(
            table="call_records",
            pattern_column="location",
            entity_type="Location",
            min_frequency=2
        )
        for proposal in location_proposals[:3]:
            print(f"   {proposal['label']}: frequency {proposal['properties']['frequency']}")

    print("\n" + "="*60)
    print("✅ Demonstration complete!")
    print("="*60)
    print(f"\nTo use with the Graph Review Agent:")
    print(f"1. Start backend with DuckDB path:")
    print(f"   export DUCKDB_PATH={db_path}")
    print(f"   uv run python -m knowledge_graph.webservice")
    print(f"\n2. Agent will have access to all DuckDB tools")
    print(f"3. Ask: 'Analyze the call_records table and propose nodes'")


if __name__ == "__main__":
    demonstrate_tools()
