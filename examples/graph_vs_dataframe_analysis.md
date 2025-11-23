# Graph vs DataFrame for Entity Resolution: When to Use What

## Executive Summary

**TL;DR: Use graphs when relationships matter. Lance-graph gives you both.**

For entity resolution specifically:
- ✅ **Use graph** when relationships provide context for matching (career paths, shared connections)
- ✅ **Use DataFrame** for simple property-based deduplication
- 🎯 **Best: Use both** - Lance-graph lets you query as graph, analyze as DataFrame

## Detailed Comparison

### Graph Advantages for Entity Resolution

#### 1. **Relationship Context Improves Accuracy**

```cypher
// Find if two "John Smith" entities worked at same companies
MATCH (p1:Entity {name: "John Smith"})-[:WORKS_AT]->(org:Organization)
      <-[:WORKS_AT]-(p2:Entity {name: "John Smith"})
WHERE p1.entity_id < p2.entity_id
RETURN p1.email, p2.email, COLLECT(org.name) AS shared_companies
```

**Why this matters**: Two people with the same name who worked at Google → Apple → Microsoft in the same timeframe are almost certainly the same person. This is **hard to capture in a flat table**.

#### 2. **Career Path Validation**

```cypher
// Does this career progression make sense?
MATCH path = (p:Person)-[:WORKS_AT*]->(orgs:Organization)
WHERE p.entity_id = 'person_123'
RETURN [rel IN relationships(path) | rel.start_date] AS dates,
       [org IN nodes(path) | org.name] AS companies
ORDER BY dates
```

**Use case**: Detect impossible timelines (overlapping jobs, illogical progressions) that suggest separate people.

#### 3. **Network-Based Duplicate Detection**

```cypher
// Find entity pairs with many mutual connections
MATCH (p1:Person)-[:KNOWS]->(mutual:Person)<-[:KNOWS]-(p2:Person)
WHERE p1.entity_id < p2.entity_id
WITH p1, p2, COUNT(DISTINCT mutual) AS shared_contacts
WHERE shared_contacts > 5
RETURN p1.name, p1.email, p2.name, p2.email, shared_contacts
ORDER BY shared_contacts DESC
```

**Why this works**: If two entities share 10+ contacts, they're likely the same person (or at minimum, you should review).

#### 4. **Multi-Hop Reasoning**

```cypher
// Find indirect connections that suggest duplicates
MATCH (p1:Person)-[:RELATIONSHIP*1..3]-(p2:Person)
WHERE p1.name CONTAINS 'Alice' AND p2.name CONTAINS 'Alice'
  AND p1.entity_id < p2.entity_id
WITH p1, p2, COUNT(*) AS connection_strength
WHERE connection_strength > 3
RETURN p1, p2, connection_strength
```

**Example**: Alice_1 worked with Bob, Bob worked with Carol, Carol worked with Alice_2 → suggests Alice_1 = Alice_2.

#### 5. **Graph Algorithms**

```python
# Community detection to find clusters of duplicates
import networkx as nx

# Convert lance-graph to NetworkX
G = nx.Graph()
# Add edges for potential duplicates
for match in potential_duplicates:
    G.add_edge(match.entity_1, match.entity_2, weight=match.confidence)

# Find connected components (clusters of duplicates)
clusters = list(nx.connected_components(G))

# Each cluster should be merged into one entity
for cluster in clusters:
    canonical_id = min(cluster)  # Pick one as canonical
    merge_ids = list(cluster - {canonical_id})
    merge_entities(canonical_id, merge_ids)
```

### DataFrame Advantages

#### 1. **Simpler Mental Model**

```python
import pandas as pd

# Simple exact duplicate removal
df = pd.DataFrame(contacts)
df.drop_duplicates(subset=['email'], keep='first', inplace=True)
```

**When to use**: Simple, property-based deduplication with no relationships.

#### 2. **Better for Aggregations**

```python
# Group by normalized name, find duplicates
df['name_normalized'] = df['name'].str.lower().str.strip()
duplicates = df.groupby('name_normalized').filter(lambda x: len(x) > 1)
```

#### 3. **ML Pipeline Integration**

```python
# Feature engineering for ML-based entity resolution
features = df.merge(df, on='phone', suffixes=('_1', '_2'))
features['name_similarity'] = features.apply(
    lambda row: fuzz.ratio(row['name_1'], row['name_2']), axis=1
)

# Train classifier
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier()
model.fit(features, labels)
```

#### 4. **Performance for Bulk Operations**

```python
# Normalize millions of phone numbers at once
df['phone_normalized'] = df['phone'].str.replace(r'\D', '', regex=True)

# Much faster than individual graph queries
```

### The Hybrid Approach (Recommended)

**Lance-graph enables the best of both worlds:**

```python
from knowledge_graph import create_default_service
import pandas as pd

service = create_default_service()

# 1. Use Cypher for complex relationship queries
query = """
MATCH (p:Person)-[:WORKS_AT]->(o:Organization)
WHERE o.name = 'TechCorp'
RETURN p.name, p.email, p.phone
"""
result = service.run(query)  # Returns PyArrow Table

# 2. Convert to pandas for analysis
df = result.to_pandas()

# 3. Do DataFrame operations (ML, stats, etc.)
df['phone_normalized'] = df['p.phone'].str.replace(r'\D', '', regex=True)
duplicates = df[df.duplicated(subset=['phone_normalized'], keep=False)]

# 4. Back to graph for relationship-aware processing
for idx, row in duplicates.iterrows():
    # Use graph context to validate matches
    context_query = f"""
    MATCH (p:Person {{email: '{row['p.email']}'}})-[:WORKS_AT]->(org)
    RETURN COUNT(org) AS num_companies
    """
    context = service.run(context_query)
    # Make smarter decisions based on graph structure
```

## When Graph Analysis Makes Sense ✅

### Use Case 1: Career Path Tracking
**Problem**: Same person across multiple companies with changing contact info.
**Why graph**: Temporal relationships (job sequence) validate identity.

```cypher
MATCH path = (p:Person)-[:WORKS_AT]->(companies:Organization)
WHERE p.name = 'Alice Smith'
RETURN path
ORDER BY [rel IN relationships(path) | rel.start_date]
```

### Use Case 2: Social Network Deduplication
**Problem**: Disambiguate common names (John Smith, Maria Garcia).
**Why graph**: Mutual friends provide strong signal.

```cypher
MATCH (p1:Person {name: 'John Smith'})-[:FRIEND_OF]->(mutual)<-[:FRIEND_OF]-(p2:Person {name: 'John Smith'})
WITH p1, p2, COUNT(mutual) AS shared_friends
WHERE shared_friends > 10
RETURN p1, p2  // Likely same person
```

### Use Case 3: Organization Hierarchy
**Problem**: Merge subsidiary/parent companies.
**Why graph**: Tree structure of ownership.

```cypher
MATCH (sub:Organization)-[:SUBSIDIARY_OF*]->(parent:Organization)
WHERE sub.name CONTAINS 'Google'
RETURN sub, parent
```

### Use Case 4: Event Attendance
**Problem**: Duplicate event records.
**Why graph**: Attendee overlap suggests same event.

```cypher
MATCH (e1:Event)-[:ATTENDED_BY]->(person:Person)<-[:ATTENDED_BY]-(e2:Event)
WHERE e1.name CONTAINS 'KDD' AND e2.name CONTAINS 'KDD'
  AND abs(duration.between(e1.date, e2.date).days) < 7
WITH e1, e2, COUNT(person) AS shared_attendees
WHERE shared_attendees > 50
RETURN e1, e2  // Likely same conference
```

## When DataFrame is Sufficient ⚠️

### Use Case 1: Exact Deduplication
**Problem**: Remove exact duplicates from CSV import.
**Why DataFrame**: Simple, no relationships needed.

```python
df.drop_duplicates(subset=['email', 'phone'], keep='first')
```

### Use Case 2: Property-Based Matching Only
**Problem**: Merge records based solely on SSN or unique ID.
**Why DataFrame**: No graph context needed.

```python
df.groupby('ssn').first()  # Keep first record per SSN
```

### Use Case 3: Statistical Analysis
**Problem**: Analyze duplicate rates, clustering statistics.
**Why DataFrame**: Better tools for stats.

```python
df.groupby('name_normalized').size().describe()
df['phone_normalized'].value_counts()
```

## Decision Matrix

| Scenario | Graph | DataFrame | Hybrid |
|----------|-------|-----------|--------|
| **Simple exact match dedup** | ❌ | ✅ | ⚪ |
| **Fuzzy name matching only** | ❌ | ✅ | ⚪ |
| **Career path validation** | ✅ | ❌ | ✅ |
| **Shared connections matter** | ✅ | ❌ | ✅ |
| **Multi-hop relationships** | ✅ | ❌ | ⚪ |
| **ML feature engineering** | ❌ | ✅ | ✅ |
| **Bulk property operations** | ❌ | ✅ | ✅ |
| **Complex pattern matching** | ✅ | ❌ | ⚪ |
| **Real-time incremental** | ✅ | ⚪ | ✅ |
| **Batch processing** | ⚪ | ✅ | ✅ |

**Legend**: ✅ Recommended | ⚪ Possible | ❌ Not ideal

## Real-World Example: LinkedIn-Style Deduplication

### Scenario
You're building a professional network with:
- 1M+ person profiles
- 100K+ companies
- 10M+ employment relationships
- Common names everywhere

### DataFrame-Only Approach ❌

```python
# Limited to property-based matching
people_df = pd.read_csv('people.csv')
duplicates = people_df[people_df.duplicated(subset=['name', 'email'], keep=False)]

# Problem: Can't use career path, mutual connections, or company co-occurrences
```

**Limitations**:
- Can't detect: "Alice Smith (alice1@gmail.com)" = "Alice M. Smith (alice2@yahoo.com)" who both worked at Google then Facebook
- Misses: Two profiles connected to the same 50 people
- No way to validate: Career timeline makes sense

### Graph Approach ✅

```cypher
// Find duplicates using multiple signals
MATCH (p1:Person)-[:WORKS_AT]->(company:Organization)<-[:WORKS_AT]-(p2:Person)
WHERE p1.name CONTAINS 'Alice Smith'
  AND p2.name CONTAINS 'Alice Smith'
  AND p1.entity_id < p2.entity_id
WITH p1, p2, COLLECT(company.name) AS shared_companies

MATCH (p1)-[:KNOWS]->(mutual:Person)<-[:KNOWS]-(p2)
WITH p1, p2, shared_companies, COUNT(mutual) AS mutual_friends

WHERE SIZE(shared_companies) > 2 OR mutual_friends > 10

RETURN p1, p2, shared_companies, mutual_friends
ORDER BY mutual_friends DESC
```

**Advantages**:
- Uses career path overlap
- Uses social graph
- Validates timeline consistency
- Produces high-confidence matches

### Hybrid Approach 🎯 (Best)

```python
# Step 1: DataFrame for fast exact matching
df = pd.DataFrame(entities)
df['phone_norm'] = df['phone'].str.replace(r'\D', '', regex=True)
exact_matches = df[df.duplicated(subset=['phone_norm'], keep=False)]

# Step 2: Graph for ambiguous cases
for name in ambiguous_names:
    query = f"""
    MATCH (p1:Person {{name: '{name}'}})-[:WORKS_AT]->(company)<-[:WORKS_AT]-(p2:Person {{name: '{name}'}})
    WHERE p1.entity_id < p2.entity_id
    WITH p1, p2, COUNT(company) AS shared_companies
    WHERE shared_companies > 1
    RETURN p1.email, p2.email, shared_companies
    """
    graph_matches = service.run(query).to_pandas()

# Step 3: Combine signals
final_matches = pd.concat([exact_matches, graph_matches])
```

## Performance Considerations

### Graph Query Performance

**Optimization strategies**:

```cypher
// ❌ Slow: Cartesian product
MATCH (p1:Person), (p2:Person)
WHERE p1.name = p2.name AND p1.entity_id < p2.entity_id
RETURN p1, p2

// ✅ Fast: Indexed lookup + focused traversal
MATCH (p1:Person {email: 'alice@example.com'})-[:WORKS_AT]->(org)<-[:WORKS_AT]-(p2:Person)
WHERE p1.entity_id < p2.entity_id
RETURN p1, p2

// ✅ Faster: Use blocking first
MATCH (p:Person)
WHERE p.name STARTS WITH 'A'
WITH p
MATCH (p)-[:WORKS_AT]->(org)<-[:WORKS_AT]-(other)
WHERE p.entity_id < other.entity_id
RETURN p, other
```

### DataFrame Performance

```python
# ✅ Vectorized operations are fast
df['name_lower'] = df['name'].str.lower()  # 1M rows in milliseconds

# ✅ GroupBy is optimized
duplicates = df.groupby('email').filter(lambda x: len(x) > 1)

# ❌ Avoid row iteration when possible
for idx, row in df.iterrows():  # SLOW for large datasets
    # Do something
```

## Conclusion

### Use **Graph** when:
1. Relationships provide signal for entity resolution
2. You need multi-hop reasoning
3. Career paths, social networks, or hierarchies matter
4. Pattern matching is complex

### Use **DataFrame** when:
1. Simple property-based deduplication
2. Bulk statistical operations
3. ML feature engineering
4. No relationships matter

### Use **Both (Hybrid)** when:
1. You have lance-graph (best of both worlds!)
2. Some entities need graph context, others don't
3. You want flexibility
4. Real-world entity resolution (recommended)

## Recommended Architecture

```
                    ┌─────────────────────────────────────┐
                    │     Incoming Data Stream            │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │  Fast Exact Match (DataFrame)       │
                    │  - Email, Phone, LinkedIn           │
                    │  - 90% of matches                   │
                    └──────┬───────────────────┬──────────┘
                           │                   │
                    ┌──────▼──────┐     ┌─────▼──────────┐
                    │  Auto-Link  │     │  Fuzzy Names   │
                    │  (Done)     │     │  (Ambiguous)   │
                    └─────────────┘     └────────┬───────┘
                                                 │
                                   ┌─────────────▼──────────────┐
                                   │  Graph Context Analysis     │
                                   │  - Career paths             │
                                   │  - Shared connections       │
                                   │  - Timeline validation      │
                                   └──────┬──────────┬───────────┘
                                          │          │
                                   ┌──────▼─────┐  ┌▼────────────┐
                                   │ Auto-Merge │  │   Human     │
                                   │  (>95%)    │  │  Review     │
                                   └────────────┘  │ (70-95%)    │
                                                   └─────────────┘
```

**Lance-graph enables this entire pipeline in one system.**
