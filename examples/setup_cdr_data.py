#!/usr/bin/env python3
"""Script to set up example CDR data for testing the Graph Review UI."""

import pyarrow as pa
from datetime import datetime, timedelta
import random

from knowledge_graph import LanceKnowledgeGraph, LanceGraphStore, KnowledgeGraphConfig


def create_sample_cdr_data():
    """Create sample Call Data Record data for testing."""

    # Sample people
    people = pa.table({
        "person_id": [1, 2, 3, 4, 5],
        "name": ["John Doe", "Sarah Chen", "Mike Johnson", "Alice Brown", "Bob Wilson"],
        "phone": ["555-0199", "555-1024", "555-2048", "555-3072", "555-4096"],
        "email": [
            "john.doe@email.com",
            "sarah.chen@email.com",
            "mike.j@email.com",
            "alice.b@email.com",
            "bob.w@email.com"
        ],
        "address": [
            "123 Main St, Arlington, VA",
            "1842 Oak St, Arlington, VA",
            "456 Elm Ave, McLean, VA",
            "789 Pine Rd, Fairfax, VA",
            "321 Maple Dr, Alexandria, VA"
        ],
    })

    # Sample phones
    phones = pa.table({
        "number": [
            "555-0199", "555-1024", "555-2048", "555-3072", "555-4096",
            "555-5120", "555-6144", "555-7168"
        ],
        "carrier": [
            "Verizon", "Verizon", "AT&T", "T-Mobile", "Verizon",
            "AT&T", "T-Mobile", "Verizon"
        ],
        "type": [
            "mobile", "mobile", "mobile", "mobile", "landline",
            "mobile", "mobile", "mobile"
        ],
        "registered_name": [
            "John Doe", "Sarah Chen", "Mike Johnson", "Alice Brown", "Bob Wilson",
            None, None, None
        ],
        "status": [
            "active", "active", "active", "active", "active",
            "active", "inactive", "active"
        ],
    })

    # Sample locations
    locations = pa.table({
        "location_id": [1, 2, 3, 4, 5],
        "address": [
            "123 Main St",
            "1842 Oak St",
            "456 Elm Ave",
            "789 Pine Rd",
            "321 Maple Dr"
        ],
        "city": [
            "Arlington", "Arlington", "McLean", "Fairfax", "Alexandria"
        ],
        "state": ["VA", "VA", "VA", "VA", "VA"],
        "zip": ["22201", "22202", "22101", "22030", "22301"],
        "type": ["residence", "residence", "residence", "business", "residence"],
    })

    # Generate call records (CONTACTED relationships)
    base_time = datetime.now() - timedelta(days=90)

    call_records = []
    phone_pairs = [
        ("555-0199", "555-1024", 47),  # John to Sarah - high frequency
        ("555-0199", "555-2048", 12),  # John to Mike
        ("555-1024", "555-2048", 8),   # Sarah to Mike
        ("555-1024", "555-3072", 5),   # Sarah to Alice
        ("555-2048", "555-4096", 15),  # Mike to Bob
        ("555-0199", "555-5120", 3),   # John to unknown
        ("555-1024", "555-5120", 2),   # Sarah to unknown
    ]

    for from_phone, to_phone, call_count in phone_pairs:
        for i in range(call_count):
            timestamp = base_time + timedelta(
                days=random.randint(0, 90),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            duration = random.randint(30, 600)  # 30s to 10min

            call_records.append({
                "from": from_phone,
                "to": to_phone,
                "timestamp": timestamp.isoformat(),
                "duration": duration,
                "direction": random.choice(["outgoing", "incoming"]),
                "call_type": random.choice(["voice", "voice", "voice", "sms"]),
            })

    contacted = pa.table({
        "from": [r["from"] for r in call_records],
        "to": [r["to"] for r in call_records],
        "timestamp": [r["timestamp"] for r in call_records],
        "duration": [r["duration"] for r in call_records],
        "direction": [r["direction"] for r in call_records],
        "call_type": [r["call_type"] for r in call_records],
    })

    # Ownership relationships
    owned_by = pa.table({
        "from": ["555-0199", "555-1024", "555-2048", "555-3072", "555-4096"],
        "to": [1, 2, 3, 4, 5],
        "registered_date": [
            "2020-01-15",
            "2019-05-20",
            "2021-03-10",
            "2018-11-05",
            "2015-07-22"
        ],
        "verified": [True, True, True, True, False],
    })

    # Location relationships
    located_at = pa.table({
        "from": ["555-0199", "555-1024", "555-2048", "555-3072", "555-4096"],
        "to": [1, 2, 3, 4, 5],
        "timestamp": [
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ],
        "confidence": [0.95, 0.92, 0.88, 0.78, 0.85],
        "method": ["gps", "gps", "tower", "tower", "ip"],
    })

    return {
        "Person": people,
        "Phone": phones,
        "Location": locations,
        "CONTACTED": contacted,
        "OWNED_BY": owned_by,
        "LOCATED_AT": located_at,
    }


def main():
    """Initialize the knowledge graph with sample CDR data."""
    print("Setting up sample CDR data...")

    # Create configuration
    config = KnowledgeGraphConfig.default()

    # Create service
    storage = LanceGraphStore(config)

    # Initialize storage
    storage.init_storage()

    print("Creating sample data...")
    datasets = create_sample_cdr_data()

    # Store datasets
    for name, table in datasets.items():
        print(f"Storing {name} ({table.num_rows} rows)...")
        storage.upsert_table(name, table, merge=False)

    print("\nSample data created successfully!")
    print("\nYou can now:")
    print("1. Start the backend: cd python && uv run python -m knowledge_graph.webservice")
    print("2. Start the frontend: cd web && npm run dev")
    print("3. Try asking the agent: 'Analyze the call patterns for 555-0199'")

    # Test query
    print("\nTesting query...")
    graph_config = config.load_graph_config()
    service = LanceKnowledgeGraph(graph_config, storage=storage)

    result = service.query("MATCH (p:Person) RETURN p.name as name LIMIT 5")
    print(f"Found {len(result.to_pylist())} people:")
    for row in result.to_pylist():
        print(f"  - {row['name']}")


if __name__ == "__main__":
    main()
