# Entity Resolution System Design for Lance-Graph

## Overview

This document describes the architecture and design of an entity resolution system built on lance-graph for identifying and merging duplicate entities across a knowledge graph.

## Use Case: Person Contact Information Across Company Moves

A common entity resolution challenge is tracking a person's identity as they change jobs:
- **Different email addresses** at each company
- **Varying name formats** (formal vs. abbreviated)
- **Same phone number** or LinkedIn profile
- **Multiple employment records** that should connect to one person

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Entity Resolution System                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Data Ingestion Layer                                     │
│     ├── Raw record parsing                                   │
│     ├── Entity extraction (Person, Org, Event)               │
│     ├── Embedding generation                                 │
│     └── Graph construction                                   │
│                                                               │
│  2. Duplicate Detection Layer                                │
│     ├── Exact matching (email, phone, LinkedIn)              │
│     ├── Fuzzy name matching                                  │
│     ├── Semantic similarity (embeddings)                     │
│     └── Graph context analysis                               │
│                                                               │
│  3. Merge Suggestion Engine                                  │
│     ├── Confidence scoring                                   │
│     ├── Context enrichment                                   │
│     └── Human-readable explanations                          │
│                                                               │
│  4. Merge Execution Layer                                    │
│     ├── Property merging strategies                          │
│     ├── Relationship reassignment                            │
│     └── Deduplication                                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         │                                          │
         ▼                                          ▼
┌──────────────────┐                    ┌──────────────────────┐
│  Lance-Graph     │                    │  Knowledge Graph     │
│  Query Engine    │◄──────────────────►│  Storage (Lance)     │
│  (Cypher)        │                    │                      │
└──────────────────┘                    └──────────────────────┘
```

## Key Features

### 1. Multi-Strategy Duplicate Detection

The system employs multiple strategies in parallel:

#### Strategy 1: Exact Identifier Matching
- **Email addresses**: Direct comparison
- **Phone numbers**: Normalized (digits only) comparison
- **LinkedIn profiles**: URL comparison
- **Confidence**: 100% when matched

#### Strategy 2: Fuzzy Name Matching
- **Normalization**: Remove titles (Dr., Mr., etc.), punctuation, extra spaces
- **Token overlap**: Handle middle name variations
  - "Alice M. Smith" ↔ "Alice Smith" = high match
  - "A. Smith" ↔ "Alice Smith" = medium match
- **Confidence**: Based on token overlap ratio

#### Strategy 3: Semantic Similarity
- **Embeddings**: Generated from name + contextual info
- **Cosine similarity**: Vector comparison
- **Threshold**: Configurable (default 0.85)
- **Advantages**: Handles typos, nicknames, cultural variations

#### Strategy 4: Graph Context Analysis
- **Shared relationships**: Do they work at the same companies?
- **Connection patterns**: Similar network structure
- **Temporal context**: Employment timeline overlap
- **Jaccard similarity**: Intersection / Union of connections

### 2. Confidence Scoring

Each match receives a weighted confidence score:

```python
# Exact matches weighted 2x
# Fuzzy/semantic matches weighted 1x
confidence = Σ(score_i × weight_i) / Σ(weight_i)
```

**Example**:
- Same LinkedIn (exact): 1.0 × 2.0 = 2.0
- Same phone (exact): 1.0 × 2.0 = 2.0
- Name similarity 0.9: 0.9 × 1.0 = 0.9
- Semantic similarity 0.87: 0.87 × 1.0 = 0.87
- **Final confidence**: 5.77 / 5.0 = 0.954 (95.4%)

### 3. Merge Strategies

Three strategies for combining duplicate entities:

#### prefer_keep (Conservative)
- Keep all properties from the canonical entity
- Discard duplicate entity properties
- **Use when**: Canonical entity is most trusted

#### prefer_complete (Recommended)
- Keep canonical entity properties
- Fill in missing values from duplicates
- **Use when**: Want most complete profile

#### merge_all (Aggressive)
- Combine all unique values
- Track alternatives in context field
- **Use when**: Need full audit trail

### 4. Relationship Management

When merging entities:
1. **Reassign relationships**: Point all edges to canonical entity
2. **Deduplicate**: Remove duplicate relationships
3. **Preserve context**: Maintain relationship properties (dates, descriptions)

**Example**:
```
Before merge:
  Alice_1 --[WORKS_AT: 2020-2022]--> TechCorp
  Alice_2 --[WORKS_AT: 2022-2024]--> Innovate Labs

After merge:
  Alice --[WORKS_AT: 2020-2022]--> TechCorp
  Alice --[WORKS_AT: 2022-2024]--> Innovate Labs
```

## Data Model

### Entity Schema

```python
{
    "entity_id": str,          # Unique identifier
    "name": str,               # Display name
    "entity_type": str,        # PERSON, ORGANIZATION, EVENT
    "context": str,            # Freeform context
    "embedding": List[float],  # Semantic vector
    "name_lower": str,         # Normalized name

    # PERSON-specific fields
    "email": Optional[str],
    "phone": Optional[str],
    "linkedin": Optional[str],
}
```

### Relationship Schema

```python
{
    "source_entity_id": str,
    "target_entity_id": str,
    "relationship_type": str,  # WORKS_AT, KNOWS, ATTENDED, etc.
    "description": str,

    # WORKS_AT-specific fields
    "job_title": Optional[str],
    "start_date": Optional[str],
    "end_date": Optional[str],
}
```

## Workflow

### End-to-End Process

```
1. Ingest Raw Data
   ├── Parse contact records
   ├── Extract entities (Person, Organization)
   ├── Generate embeddings
   └── Create relationships

2. Find Duplicates
   ├── Load all entities of target type
   ├── Compare pairwise using all strategies
   ├── Score matches
   └── Rank by confidence

3. Generate Suggestions
   ├── Filter by confidence threshold
   ├── Enrich with relationship context
   └── Format for human review

4. Execute Merges
   ├── Choose merge strategy
   ├── Combine entity properties
   ├── Reassign relationships
   ├── Deduplicate edges
   └── Write back to storage

5. Verify Results
   └── Query final state
```

## Usage Examples

### Basic Usage

```python
from entity_resolution import EntityResolver, RawContactRecord
from knowledge_graph import create_default_service

# Initialize
service = create_default_service()
service.ensure_initialized()
resolver = EntityResolver(service)

# Ingest data
records = [
    RawContactRecord(
        name="Alice Smith",
        email="alice@company1.com",
        phone="555-0123",
        company="Company 1"
    ),
    RawContactRecord(
        name="Alice M. Smith",
        email="alice@company2.com",
        phone="555-0123",
        company="Company 2"
    )
]
resolver.ingest_contact_records(records)

# Find duplicates
matches = resolver.find_duplicate_candidates()
for match in matches:
    print(f"Confidence: {match.similarity_score:.2%}")
    print(f"Reasons: {match.match_reasons}")

# Get merge suggestions
suggestions = resolver.get_merge_suggestions(min_confidence=0.8)

# Execute merge
if suggestions:
    result = resolver.merge_entities(
        keep_id=suggestions[0]['entity_1']['id'],
        merge_ids=[suggestions[0]['entity_2']['id']],
        merge_strategy="prefer_complete"
    )
    print(f"Merged {result['entities_merged']} entities")
```

### Advanced: Custom Strategies

```python
# Use specific strategies only
matches = resolver.find_duplicate_candidates(
    strategies=["exact_email", "graph_context"]
)

# Adjust similarity threshold
resolver = EntityResolver(
    service=service,
    similarity_threshold=0.90  # More strict
)

# Custom merge logic
def custom_merge(keep_entity, merge_entities):
    merged = keep_entity.copy()
    # Your custom logic here
    return merged
```

## Performance Considerations

### Scalability

- **Pairwise comparison**: O(n²) for n entities
- **Optimization**: Use blocking strategies
  - Group by first letter of name
  - Group by organization
  - Pre-filter by type

### Embedding Generation

- **Batch processing**: Generate embeddings in batches
- **Caching**: Store embeddings in entity table
- **Model choice**: Balance quality vs. speed
  - Fast: `text-embedding-3-small`
  - Quality: `text-embedding-3-large`

### Storage

- **Lance datasets**: Columnar format for efficient queries
- **Indexes**: Create indexes on frequently queried fields
- **Partitioning**: Partition by entity_type for large graphs

## Best Practices

### 1. Data Quality
- Normalize data during ingestion
- Validate email/phone formats
- Handle missing values gracefully

### 2. Threshold Tuning
- Start conservative (high threshold)
- Analyze false positives/negatives
- Adjust per use case

### 3. Human-in-the-Loop
- Auto-merge only high-confidence (>95%)
- Review medium-confidence (70-95%)
- Provide clear explanations

### 4. Audit Trail
- Log all merges
- Preserve original entity IDs
- Enable undo functionality

## Extensions

### Future Enhancements

1. **Blocking Strategies**: Reduce pairwise comparisons
2. **Active Learning**: Learn from user feedback
3. **Temporal Analysis**: Consider date patterns
4. **Cross-type Resolution**: Link Person → Email → Account
5. **Clustering**: Find groups of related duplicates
6. **Confidence Calibration**: ML-based scoring

### Integration Points

- **ETL Pipelines**: Batch processing of new data
- **Real-time API**: Online duplicate detection
- **UI Dashboard**: Merge review interface
- **Monitoring**: Track merge statistics

## References

- [Lance-Graph Documentation](https://github.com/lancedb/lance-graph)
- [Entity Resolution Techniques](https://en.wikipedia.org/wiki/Record_linkage)
- [Cypher Query Language](https://neo4j.com/developer/cypher/)
