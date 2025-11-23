# Pydantic-Based Entity Resolution Guide

## Why Pydantic Models?

Using Pydantic models to define entity resolution strategies provides:

✅ **Self-documenting code** - Field metadata explicitly shows matching/merging logic
✅ **Type safety** - Runtime validation catches errors early
✅ **Easy updates** - Change metadata in one place, logic updates everywhere
✅ **Clear separation** - Strict (exact) vs fuzzy matching is explicit
✅ **Testable** - Clear schema makes unit testing straightforward
✅ **JSON schema generation** - Auto-generate API documentation
✅ **IDE support** - Autocomplete and type hints improve developer experience

## Core Concepts

### 1. Match Strategy (How to Compare Fields)

```python
class MatchStrategy(str, Enum):
    EXACT = "exact"              # Must match exactly (email, SSN)
    NORMALIZED = "normalized"     # Match after normalization (phone)
    FUZZY = "fuzzy"              # Similarity-based (name, address)
    SEMANTIC = "semantic"         # Embedding-based similarity
    IGNORE = "ignore"            # Don't use for matching
```

### 2. Merge Strategy (How to Combine Values)

```python
class MergeStrategy(str, Enum):
    KEEP = "keep"                       # Keep canonical value
    PREFER_NON_NULL = "prefer_non_null" # Fill in missing values
    PREFER_LONGER = "prefer_longer"     # Keep longer string
    PREFER_NEWER = "prefer_newer"       # Use most recent
    CONCATENATE = "concatenate"         # Combine all unique values
    TAKE_MAX = "take_max"              # Take maximum
    TAKE_MIN = "take_min"              # Take minimum
```

### 3. Field Metadata

Each field has metadata that drives the resolution logic:

```python
class FieldMetadata(BaseModel):
    match_strategy: MatchStrategy      # How to match
    merge_strategy: MergeStrategy      # How to merge
    match_weight: float               # Importance (0-10)
    is_blocker: bool                  # Exact match = immediate link?
    similarity_threshold: float       # For fuzzy matching
```

## Defining Your Entity Schema

### Example: Person Entity

```python
class PersonEntity(BaseModel):
    """Person with explicit field strategies"""

    # BLOCKER FIELD: Email (exact match = 100% confidence)
    email: Optional[str] = Field(
        default=None,
        description="Email address - blocker field",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.CONCATENATE,  # Keep all emails
            "is_blocker": True,        # Exact match = immediate link
            "match_weight": 5.0        # High importance
        }
    )

    # BLOCKER FIELD: Phone (normalized matching)
    phone: Optional[str] = Field(
        default=None,
        description="Phone number",
        json_schema_extra={
            "match_strategy": MatchStrategy.NORMALIZED,  # "555-0123" = "5550123"
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0
        }
    )

    # FUZZY FIELD: Name (similarity-based)
    name: str = Field(
        description="Full name",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_LONGER,  # "Alice M. Smith" over "Alice Smith"
            "match_weight": 2.0,
            "similarity_threshold": 0.8  # 80% similarity required
        }
    )

    # SUPPORTING FIELD: Date of birth
    date_of_birth: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.PREFER_NON_NULL,  # Fill in if missing
            "match_weight": 3.0
        }
    )

    # METADATA FIELD: Created timestamp (don't use for matching)
    created_at: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.IGNORE,  # Not used for matching
            "merge_strategy": MergeStrategy.TAKE_MIN  # Keep earliest
        }
    )
```

## How It Works

### Strict (Exact) vs Fuzzy Matching - Crystal Clear

**Before (implicit logic in code):**
```python
# Hard to understand what's exact vs fuzzy
if entity1.email == entity2.email:  # Is this a blocker?
    return True  # How confident?

if calculate_similarity(entity1.name, entity2.name) > 0.8:  # Why 0.8?
    # What about other fields?
    pass
```

**After (explicit in schema):**
```python
# The schema tells you everything!
email_metadata = PersonEntity.get_field_metadata("email")
# Returns: MatchStrategy.EXACT, is_blocker=True, weight=5.0

name_metadata = PersonEntity.get_field_metadata("name")
# Returns: MatchStrategy.FUZZY, threshold=0.8, weight=2.0

# Matching logic automatically uses metadata
decision = resolver.should_merge(candidate, existing)
# Automatically checks blockers first, then fuzzy fields
```

### Automatic Resolution Driven by Schema

```python
resolver = PydanticEntityResolver(PersonEntity)

# The resolver automatically:
# 1. Checks all blocker fields first (email, phone, SSN)
# 2. If blocker matches → immediate high confidence
# 3. Then checks fuzzy fields with proper thresholds
# 4. Weights scores according to field importance
# 5. Returns decision based on thresholds

decision = resolver.should_merge(candidate, existing)
# Decision contains:
#   - action: "merge_with" | "needs_review" | "create_new"
#   - confidence: 0.0 to 1.0
#   - match_reasons: detailed explanation per field
```

## Real-World Examples

### Example 1: Email Match (100% Confidence)

**Incoming:**
```python
candidate = PersonEntity(
    entity_id="temp",
    name="Alice M. Smith",      # Different from existing
    email="alice@techcorp.com", # SAME as existing
    phone="555-9999"            # Different from existing
)

existing = PersonEntity(
    entity_id="person_001",
    name="Alice Smith",
    email="alice@techcorp.com",
    phone="555-0123"
)
```

**Result:**
```
Decision: MERGE_WITH
Confidence: 100%
Reason: Exact match on blocker field 'email'
```

**Why:** Email is marked as `is_blocker=True` with `match_strategy=EXACT`. One exact blocker match = immediate high confidence.

### Example 2: Phone + Name Match (High Confidence)

**Incoming:**
```python
candidate = PersonEntity(
    name="Alice Smith",         # Same name
    email="alice@personal.com", # Different email
    phone="555-0123"            # SAME phone (blocker)
)
```

**Result:**
```
Decision: MERGE_WITH
Confidence: 100%
Reasons:
  • phone: Exact match on blocker (weight: 5.0 × 2.0 = 10.0)
  • name: Fuzzy match 100% (weight: 2.0)
```

**Why:** Phone blocker matched + name similarity 100% = very high weighted score.

### Example 3: Ambiguous (Needs Review)

**Incoming:**
```python
candidate = PersonEntity(
    name="Alicia Smith",        # Similar to "Alice Smith" (typo?)
    email="alicia@email.com",   # Different
    phone="555-7777"            # Different
)
```

**Result:**
```
Decision: NEEDS_REVIEW
Confidence: 53%
Reasons:
  • name: Fuzzy match 67% (below threshold)
```

**Why:** No blocker matches, only partial name similarity. Confidence between 70-95% threshold = flag for human review.

## Merge Behavior - Also Explicit!

### Merging Multiple Entities

```python
canonical = PersonEntity(
    entity_id="person_001",
    name="Alice Smith",
    email="alice@techcorp.com"
)

duplicate1 = PersonEntity(
    entity_id="person_002",
    name="Alice M. Smith",       # Longer name
    email="alice@newco.com"      # Different email
)

duplicate2 = PersonEntity(
    entity_id="person_003",
    email="asmith@startup.com",  # Another email
    address="123 Main St"        # New info
)

result = resolver.merge_entities(canonical, [duplicate1, duplicate2])
```

**Merged Entity:**
```python
{
    "entity_id": "person_001",           # KEEP (canonical)
    "name": "Alice M. Smith",            # PREFER_LONGER
    "email": "alice@techcorp.com, alice@newco.com, asmith@startup.com",  # CONCATENATE
    "address": "123 Main St"             # PREFER_NON_NULL
}
```

**Log shows what happened:**
```
Field merge details:
  • entity_id: keep (canonical ID preserved)
  • name: prefer_longer (chose "Alice M. Smith")
  • email: concatenate (kept all 3 emails)
  • address: prefer_non_null (filled in missing value)
```

## Updating Match Logic is Easy

### Adding a New Blocker Field

Want to add LinkedIn as a strong identifier?

**Before (scattered logic):**
- Update matching function
- Update merge function
- Update tests
- Update documentation
- Hope you didn't miss anything

**After (one place):**
```python
class PersonEntity(BaseModel):
    # Just add the field with metadata!
    linkedin: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 5.0
        }
    )

# That's it! The resolver automatically:
# - Checks LinkedIn during matching
# - Weights it properly
# - Uses it as a blocker
```

### Adjusting Thresholds

```python
# Change name similarity threshold from 0.8 to 0.85
name: str = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.FUZZY,
        "similarity_threshold": 0.85  # Changed from 0.8
    }
)

# That's it - all matching logic updates automatically
```

### Changing Merge Behavior

```python
# Change email from CONCATENATE to KEEP
email: Optional[str] = Field(
    json_schema_extra={
        "merge_strategy": MergeStrategy.KEEP  # Changed from CONCATENATE
    }
)

# Now when merging, only canonical email is kept
```

## Different Entities, Different Strategies

### Organization Entity

Organizations need different matching logic:

```python
class OrganizationEntity(BaseModel):
    name: str = Field(
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "similarity_threshold": 0.85,  # Higher than person names
            "match_weight": 3.0
        }
    )

    domain: Optional[str] = Field(
        default=None,
        description="Website domain (google.com)",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,  # google.com = strong signal
            "is_blocker": True,
            "match_weight": 5.0
        }
    )

    tax_id: Optional[str] = Field(
        default=None,
        description="Tax ID / EIN",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "is_blocker": True,
            "match_weight": 10.0  # Strongest blocker
        }
    )
```

**Usage:**
```python
org_resolver = PydanticEntityResolver(OrganizationEntity)

# Automatically uses org-specific matching logic
decision = org_resolver.should_merge(candidate_org, existing_org)
```

## Configuration and Thresholds

### Global Configuration

```python
config = ResolutionConfig(
    auto_merge_threshold=0.95,     # Auto-merge if >= 95%
    review_threshold=0.70,         # Review if 70-95%
    blocker_exact_match_weight=2.0 # Blockers weighted 2x
)

resolver = PydanticEntityResolver(PersonEntity, config=config)
```

### Decision Flow

```
Confidence >= 95% → AUTO MERGE (if enabled)
         ↓
Confidence >= 70% → FLAG FOR REVIEW
         ↓
Confidence < 70%  → CREATE NEW ENTITY
```

## Testing Made Easy

### Unit Testing

```python
def test_email_blocker():
    """Test that exact email match triggers merge"""
    entity1 = PersonEntity(
        entity_id="1",
        name="Alice Smith",
        email="alice@example.com"
    )

    entity2 = PersonEntity(
        entity_id="2",
        name="Different Name",  # Different name
        email="alice@example.com"  # SAME email
    )

    resolver = PydanticEntityResolver(PersonEntity)
    decision = resolver.should_merge(entity2, entity1)

    assert decision.action == "merge_with"
    assert decision.confidence == 1.0
    assert any(r.field == "email" for r in decision.match_reasons)
```

### Integration Testing

```python
def test_merge_keeps_all_emails():
    """Test that CONCATENATE strategy keeps all emails"""
    canonical = PersonEntity(entity_id="1", email="email1@test.com")
    dup1 = PersonEntity(entity_id="2", email="email2@test.com")
    dup2 = PersonEntity(entity_id="3", email="email3@test.com")

    resolver = PydanticEntityResolver(PersonEntity)
    result = resolver.merge_entities(canonical, [dup1, dup2])

    assert "email1@test.com" in result.merged_entity["email"]
    assert "email2@test.com" in result.merged_entity["email"]
    assert "email3@test.com" in result.merged_entity["email"]
```

## JSON Schema Generation

```python
# Generate JSON schema for API docs
schema = PersonEntity.model_json_schema()

# Use in FastAPI
from fastapi import FastAPI

app = FastAPI()

@app.post("/resolve")
def resolve_entity(candidate: PersonEntity, existing: PersonEntity):
    resolver = PydanticEntityResolver(PersonEntity)
    decision = resolver.should_merge(candidate, existing)
    return decision.model_dump()

# OpenAPI docs automatically show:
# - Field types
# - Validation rules
# - Descriptions
# - Match/merge strategies
```

## Comparison: Before vs After

### Before: Implicit Logic

```python
def should_merge(candidate, existing):
    # What's a blocker? What's fuzzy?
    # Why these thresholds?
    # How are fields weighted?

    if candidate['email'] == existing['email']:
        return True  # Is this 100% confidence?

    if calculate_name_similarity(candidate['name'], existing['name']) > 0.8:
        if candidate.get('phone') == existing.get('phone'):
            return True  # What confidence?

    # ... more unclear logic
    return False
```

**Problems:**
- Logic scattered across functions
- No clear separation of exact vs fuzzy
- Thresholds are magic numbers
- Hard to test
- Difficult to update

### After: Explicit Schema-Driven

```python
# Everything explicit in schema
email: Optional[str] = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.EXACT,
        "is_blocker": True,
        "match_weight": 5.0
    }
)

# Logic is automatic
resolver = PydanticEntityResolver(PersonEntity)
decision = resolver.should_merge(candidate, existing)

# Clear, documented, testable
```

**Benefits:**
- Schema is single source of truth
- Clear exact vs fuzzy distinction
- Thresholds are documented
- Easy to test
- Simple to update

## Best Practices

### 1. Start with Blockers

Identify your strongest signals first:
```python
# These are blockers (exact match = immediate link)
- email
- phone (normalized)
- ssn / tax_id
- linkedin_url
- unique_identifier
```

### 2. Weight Fields Appropriately

```python
# Strong blockers
is_blocker=True, match_weight=5.0-10.0

# Supporting evidence
match_weight=2.0-3.0

# Weak signals
match_weight=1.0
```

### 3. Set Realistic Thresholds

```python
# Names: lower threshold (typos common)
similarity_threshold=0.7-0.8

# Company names: higher threshold (more variation)
similarity_threshold=0.85-0.9
```

### 4. Choose Merge Strategies Carefully

```python
# Contact info: CONCATENATE (keep all)
email, phone → MergeStrategy.CONCATENATE

# Display info: PREFER_LONGER (more complete)
name, address → MergeStrategy.PREFER_LONGER

# Metadata: TAKE_MIN/MAX (meaningful)
created_at → MergeStrategy.TAKE_MIN (earliest)
updated_at → MergeStrategy.TAKE_MAX (latest)
```

### 5. Document Your Decisions

```python
field: str = Field(
    description="Clear description of what this field represents",
    json_schema_extra={
        "match_strategy": MatchStrategy.EXACT,
        "merge_strategy": MergeStrategy.KEEP,
        # Add comments explaining why
        # "Why exact? Because email is unique identifier"
        # "Why keep? Primary email shouldn't change"
    }
)
```

## Summary

### Key Advantages

| Aspect | Traditional | Pydantic-Based |
|--------|------------|----------------|
| **Clarity** | Logic scattered | All in schema |
| **Updates** | Change multiple places | Change metadata |
| **Testing** | Complex setup | Simple, clear |
| **Documentation** | Manual | Auto-generated |
| **Type Safety** | Runtime errors | Caught early |
| **Exact vs Fuzzy** | Implicit | Explicit |

### When to Use This Approach

✅ **Yes:**
- Multiple entity types with different rules
- Team needs clear documentation
- Requirements change frequently
- Need type safety and validation
- Want auto-generated API docs

❌ **Maybe not:**
- Very simple deduplication (email only)
- One-off script
- No need for flexibility

### Quick Reference

```python
# 1. Define your entity
class MyEntity(BaseModel):
    field: str = Field(
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,  # How to match
            "merge_strategy": MergeStrategy.KEEP,   # How to merge
            "is_blocker": True,                     # Exact match = link?
            "match_weight": 5.0,                    # Importance
            "similarity_threshold": 0.8              # For fuzzy
        }
    )

# 2. Create resolver
resolver = PydanticEntityResolver(MyEntity)

# 3. Match
decision = resolver.should_merge(candidate, existing)

# 4. Merge
result = resolver.merge_entities(canonical, duplicates)
```

## Run the Demo

```bash
python examples/pydantic_entity_resolution.py
```

This shows:
- ✅ Exact email match → auto-merge (100%)
- ✅ Phone + name match → auto-merge (100%)
- ⚠️ Name similarity only → needs review
- 🔄 Merging with different strategies per field

---

**The Pydantic approach makes entity resolution logic explicit, maintainable, and self-documenting. Update the schema, and the behavior automatically follows!** 🎉
