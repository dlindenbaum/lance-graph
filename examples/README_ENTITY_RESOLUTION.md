# Entity Resolution System for Lance-Graph - Complete Guide

## 📚 What's Included

A comprehensive entity resolution system for identifying and merging duplicate nodes (Person, Organization, Event) in lance-graph knowledge graphs.

### Files Overview

| File | Purpose | Run It |
|------|---------|--------|
| **pydantic_entity_resolution.py** | ⭐ **Recommended** - Pydantic-based implementation | `python examples/pydantic_entity_resolution.py` |
| **PYDANTIC_ENTITY_RESOLUTION_GUIDE.md** | Comprehensive guide for Pydantic approach | [Read](PYDANTIC_ENTITY_RESOLUTION_GUIDE.md) |
| **entity_resolution_simple_demo.py** | Standalone demo (no dependencies) | `python examples/entity_resolution_simple_demo.py` |
| **incremental_entity_resolution.py** | Check-before-create workflow | `python examples/incremental_entity_resolution.py` |
| **entity_resolution.py** | Full implementation with lance-graph | Requires lance-graph build |
| **entity_resolution_design.md** | Architecture and design details | [Read](entity_resolution_design.md) |
| **graph_vs_dataframe_analysis.md** | When to use graph vs DataFrame | [Read](graph_vs_dataframe_analysis.md) |
| **ENTITY_RESOLUTION_GUIDE.md** | General usage guide | [Read](ENTITY_RESOLUTION_GUIDE.md) |

## 🚀 Quick Start

### 1. Best Approach: Pydantic-Based (Recommended)

**Why:** Explicit, type-safe, self-documenting

```bash
python examples/pydantic_entity_resolution.py
```

**What you'll see:**
```
✅ Exact email match → merge_with (100% confidence)
✅ Phone + name match → merge_with (100% confidence)
⚠️ Name similarity only → needs_review (0% confidence)
🔄 Merging 3 entities with different strategies per field
```

**Key features:**
```python
# Define field strategies in schema
class PersonEntity(BaseModel):
    email: Optional[str] = Field(
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,      # Strict matching
            "merge_strategy": MergeStrategy.CONCATENATE, # Keep all values
            "is_blocker": True,                         # Exact match = immediate link
            "match_weight": 5.0                         # High importance
        }
    )

    name: str = Field(
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,      # Fuzzy matching
            "similarity_threshold": 0.8                 # 80% similarity required
        }
    )
```

### 2. Simple Demo (No Setup Required)

```bash
python examples/entity_resolution_simple_demo.py
```

**Use case:** Person contact info across multiple company moves

**Input:** 5 contact records (same person at 3 different companies)

**Output:**
- Detected 6 potential duplicate pairs
- Auto-merged 3 entities into 1 canonical person
- Preserved all employment relationships

### 3. Incremental Resolution (Production Pattern)

```bash
python examples/incremental_entity_resolution.py
```

**Shows:** How to check for duplicates BEFORE creating new nodes

**Decision flow:**
```
New data arrives
    ↓
1. Fast exact checks (email, phone, LinkedIn)
   → If match found: LINK to existing
    ↓
2. Fuzzy name search
   → If no candidates: CREATE new
    ↓
3. Graph context scoring
   → High confidence (>95%): AUTO-MERGE
   → Medium (70-95%): FLAG FOR REVIEW
   → Low (<70%): CREATE new
```

## 📖 Key Concepts

### Strict vs Fuzzy Matching - Now Crystal Clear!

#### ✅ With Pydantic (Explicit)

```python
# Email: STRICT (exact match required)
email: Optional[str] = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.EXACT,
        "is_blocker": True  # Exact match = immediate link
    }
)

# Name: FUZZY (similarity-based)
name: str = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.FUZZY,
        "similarity_threshold": 0.8  # 80% similar
    }
)
```

**Benefits:**
- ✅ Self-documenting
- ✅ Easy to update (change metadata, logic updates)
- ✅ Type-safe
- ✅ Clear at a glance

#### ❌ Without Pydantic (Implicit)

```python
# Which fields are exact? Which are fuzzy? Who knows!
if entity1.email == entity2.email:  # Is this a blocker?
    return True  # What confidence?

if name_similarity > 0.8:  # Why 0.8?
    # ...
```

### Multi-Strategy Matching

The system uses **5 complementary strategies**:

1. **Exact Identifier Matching** (email, SSN, LinkedIn) → 100% confidence
2. **Normalized Matching** (phone: "555-0123" = "5550123")
3. **Fuzzy Matching** (name: "Alice M. Smith" ↔ "Alice Smith" = 67%)
4. **Graph Context** (shared companies, connections)
5. **Semantic Similarity** (embeddings, handles typos)

### Merge Strategies Per Field

```python
# Keep all emails (person may have multiple)
email → MergeStrategy.CONCATENATE
# Result: "alice@techcorp.com, alice@newco.com, asmith@startup.com"

# Keep longer name (more complete)
name → MergeStrategy.PREFER_LONGER
# Result: "Alice M. Smith" beats "Alice Smith"

# Fill in missing values
address → MergeStrategy.PREFER_NON_NULL
# Result: Take first non-null value

# Keep earliest creation date
created_at → MergeStrategy.TAKE_MIN

# Keep latest update
updated_at → MergeStrategy.TAKE_MAX
```

## 🎯 Your Questions Answered

### Q: Graph vs DataFrame - Which to Use?

**A: Use graph because relationships improve accuracy. Lance-graph gives you both!**

See: [graph_vs_dataframe_analysis.md](graph_vs_dataframe_analysis.md)

**Graph wins when:**
- ✅ Career paths validate identity (TechCorp → Startup → BigCorp)
- ✅ Shared connections matter (worked with same 10 people)
- ✅ Timeline analysis (detect impossible overlaps)
- ✅ Multi-hop reasoning

**Hybrid approach (recommended):**
```python
# Fast exact matching with DataFrame operations
df['phone_norm'] = df['phone'].str.replace(r'\D', '', regex=True)
exact_matches = df[df.duplicated(subset=['phone_norm'])]

# Graph for ambiguous cases
query = """
MATCH (p1:Person)-[:WORKS_AT]->(org)<-[:WORKS_AT]-(p2:Person)
WHERE p1.name = 'John Smith' AND p2.name = 'John Smith'
WITH p1, p2, COUNT(org) AS shared_companies
WHERE shared_companies > 2
RETURN p1, p2
"""
```

### Q: How to Handle New Raw Data?

**A: Check-before-create pattern prevents duplicates upfront**

See: [incremental_entity_resolution.py](incremental_entity_resolution.py)

**Workflow:**
```python
decision = resolver.should_create_new_entity(raw_record)

if decision.action == "link_existing":
    # Same person, just update with new info (new job, new email)
    update_entity(decision.matched_entity_id, raw_record)

elif decision.action == "create_new":
    # No matches - safe to create new node
    create_entity(raw_record)

else:  # needs_review
    # Ambiguous - flag for human
    create_entity(raw_record)
    add_to_review_queue(decision)
```

**Example:**
```
Incoming: Alice M. Smith (alice@newco.com, phone: 555-0123)
Existing: Alice Smith (alice@techcorp.com, phone: 555-0123)

Step 1: Check email → No match (new job email)
Step 2: Check phone → MATCH! (555-0123)
Step 3: Check LinkedIn → MATCH!

Decision: LINK to existing (100% confidence)
Action: Add new email and company relationship to existing entity
```

### Q: Pydantic Models - Why?

**A: Makes strict vs fuzzy matching crystal clear and easy to update**

See: [PYDANTIC_ENTITY_RESOLUTION_GUIDE.md](PYDANTIC_ENTITY_RESOLUTION_GUIDE.md)

**Before:**
- Logic scattered across functions
- Unclear what's exact vs fuzzy
- Magic numbers everywhere
- Hard to update

**After:**
- All logic in schema
- Explicit strategies per field
- Self-documenting
- Change metadata → behavior updates

**Update example:**
```python
# Want LinkedIn to be a blocker? Just add metadata!
linkedin: Optional[str] = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.EXACT,
        "is_blocker": True,
        "match_weight": 5.0
    }
)

# That's it! Resolver automatically uses it.
```

## 📊 Real-World Example

### Scenario: Person Across 3 Jobs

**Input data:**
```
1. Alice M. Smith @ TechCorp (alice.smith@techcorp.com, 555-0123)
2. Alice Smith @ Innovate Labs (alice.smith@innovate.io, 555-0123)
3. A. Smith @ Stealth Startup (asmith@startup.com, 555-0123)
4. Bob Johnson @ TechCorp (bob.johnson@techcorp.com, 555-9999)
```

**Detection results:**
```
6 potential duplicate pairs found:

Match #1: Alice M. Smith ↔ A. Smith
  Confidence: 100%
  Reasons: exact_phone (555-0123), exact_linkedin

Match #2: Alice Smith ↔ A. Smith
  Confidence: 100%
  Reasons: exact_phone, exact_linkedin

Match #3: Alice M. Smith ↔ Alice Smith
  Confidence: 93.3%
  Reasons: exact_phone, exact_linkedin, fuzzy_name_0.67
```

**Merge result:**
```
Merged 3 entities into 1:
  Name: Alice M. Smith (prefer_longer)
  Email: alice.smith@techcorp.com, alice.smith@innovate.io, asmith@startup.com
  Phone: 555-0123
  Companies:
    • TechCorp (2020-2022)
    • Innovate Labs (2022-2024)
    • Stealth Startup (2024-present)

Final count: 2 unique persons (Alice + Bob)
```

## 🛠️ Implementation Patterns

### Pattern 1: Batch Processing (Clean Existing Data)

```python
# Load all entities
persons = load_all_persons()

# Find duplicates
resolver = PydanticEntityResolver(PersonEntity)
matches = []
for i, p1 in enumerate(persons):
    for p2 in persons[i+1:]:
        decision = resolver.should_merge(p2, p1)
        if decision.confidence >= 0.7:
            matches.append(decision)

# Auto-merge high confidence
for match in matches:
    if match.confidence >= 0.95:
        merge_entities(match.matched_entity_id, [match.entity_id])

# Review medium confidence
review_queue = [m for m in matches if 0.7 <= m.confidence < 0.95]
```

### Pattern 2: Incremental (Handle New Data)

```python
# New record arrives
new_person = PersonEntity(**raw_data)

# Check before creating
decision = resolver.should_create_new_entity(new_person)

if decision.action == "link_existing":
    # Update existing entity
    add_employment_record(decision.matched_entity_id, raw_data.company)
    add_email_if_new(decision.matched_entity_id, raw_data.email)

elif decision.action == "create_new":
    # Safe to create
    create_entity(new_person)

else:
    # Flag for review
    create_with_flag(new_person, decision)
```

### Pattern 3: Real-Time API

```python
from fastapi import FastAPI
from pydantic_entity_resolution import PersonEntity, PydanticEntityResolver

app = FastAPI()

@app.post("/check-duplicate")
def check_duplicate(candidate: PersonEntity):
    """Check if candidate is a duplicate of existing entity"""
    existing_matches = search_by_name(candidate.name, limit=5)

    resolver = PydanticEntityResolver(PersonEntity)
    results = []

    for existing in existing_matches:
        decision = resolver.should_merge(candidate, existing)
        if decision.confidence >= 0.7:
            results.append({
                "entity_id": existing.entity_id,
                "confidence": decision.confidence,
                "action": decision.action,
                "reasons": [r.dict() for r in decision.match_reasons]
            })

    return results
```

## 📈 Performance Tips

### 1. Use Blocking

Don't compare all O(n²) pairs. Use blocking:

```python
# Group by first letter of name
blocks = defaultdict(list)
for person in persons:
    first_letter = person.name[0].lower()
    blocks[first_letter].append(person)

# Only compare within blocks
for block in blocks.values():
    for i, p1 in enumerate(block):
        for p2 in block[i+1:]:
            check_match(p1, p2)
```

### 2. Fast Exact Checks First

```python
# Check blockers before fuzzy matching
if candidate.email and find_by_email(candidate.email):
    return immediate_link()  # Don't bother with fuzzy

# Only do expensive fuzzy matching if no exact matches
fuzzy_candidates = find_by_fuzzy_name(candidate.name)
```

### 3. Index Your Blocker Fields

```python
# Create indexes for fast lookup
CREATE INDEX ON Entity(email)
CREATE INDEX ON Entity(phone)
CREATE INDEX ON Entity(linkedin)

# Queries will be much faster
MATCH (e:Entity {email: 'alice@example.com'}) RETURN e
```

## 🧪 Testing

### Unit Tests

```python
def test_email_blocker_match():
    """Email blocker should trigger immediate merge"""
    e1 = PersonEntity(entity_id="1", email="alice@test.com")
    e2 = PersonEntity(entity_id="2", email="alice@test.com")

    resolver = PydanticEntityResolver(PersonEntity)
    decision = resolver.should_merge(e2, e1)

    assert decision.action == "merge_with"
    assert decision.confidence == 1.0
```

### Integration Tests

```python
def test_full_workflow():
    """Test complete incremental resolution workflow"""
    # 1. Create existing entity
    existing = create_person("Alice Smith", "alice@tech.com")

    # 2. New data arrives with different email, same phone
    new_data = {"name": "Alice Smith", "email": "alice@new.com", "phone": "555-0123"}

    # 3. Check if should create new
    decision = resolver.should_create_new_entity(PersonEntity(**new_data))

    # 4. Should link, not create
    assert decision.action == "link_existing"
    assert decision.matched_entity_id == existing.entity_id
```

## 📚 Further Reading

| Topic | Document |
|-------|----------|
| **Why Pydantic?** | [PYDANTIC_ENTITY_RESOLUTION_GUIDE.md](PYDANTIC_ENTITY_RESOLUTION_GUIDE.md) |
| **Graph vs DataFrame** | [graph_vs_dataframe_analysis.md](graph_vs_dataframe_analysis.md) |
| **Architecture** | [entity_resolution_design.md](entity_resolution_design.md) |
| **General Guide** | [ENTITY_RESOLUTION_GUIDE.md](ENTITY_RESOLUTION_GUIDE.md) |

## 🎯 Which File Should I Use?

### For Production Implementation

**→ Use [pydantic_entity_resolution.py](pydantic_entity_resolution.py)**

- Most maintainable
- Type-safe
- Self-documenting
- Easy to extend

### For Understanding Concepts

**→ Run [entity_resolution_simple_demo.py](entity_resolution_simple_demo.py)**

- No setup required
- Shows core algorithms
- Real-world example

### For Incremental Processing

**→ Study [incremental_entity_resolution.py](incremental_entity_resolution.py)**

- Check-before-create pattern
- Production workflow
- Decision tree

### For Full Lance-Graph Integration

**→ See [entity_resolution.py](entity_resolution.py)**

- Uses Cypher queries
- Embeddings for semantic matching
- Graph traversal

## 🚦 Next Steps

1. **Try the demos:**
   ```bash
   python examples/pydantic_entity_resolution.py
   python examples/entity_resolution_simple_demo.py
   ```

2. **Define your schema:**
   - Identify blocker fields (email, SSN, etc.)
   - Set fuzzy thresholds for names
   - Choose merge strategies

3. **Test with real data:**
   - Start with small batch
   - Tune confidence thresholds
   - Measure precision/recall

4. **Deploy incrementally:**
   - Start with check-before-create
   - Add batch cleanup later
   - Iterate based on feedback

## 💡 Pro Tips

✅ **Start conservative** - High thresholds (95%+) for auto-merge
✅ **Humans in the loop** - Review 70-95% confidence matches
✅ **Different entities need different rules** - Person vs Organization vs Event
✅ **Use blocking** - Don't compare all O(n²) pairs
✅ **Log everything** - Audit trail for all merges
✅ **Monitor metrics** - Track precision, recall, review queue size

## 🎉 Summary

You now have:

- ✅ **Pydantic-based implementation** - Type-safe, self-documenting
- ✅ **Multi-strategy matching** - Exact, fuzzy, semantic, graph context
- ✅ **Flexible merge strategies** - Per-field control
- ✅ **Incremental workflow** - Check-before-create pattern
- ✅ **Graph + DataFrame** - Best of both worlds
- ✅ **Production-ready** - Testing, validation, documentation

**All code is committed and pushed to your branch!** 🚀

Questions? Check the guides or run the demos to see it in action.
