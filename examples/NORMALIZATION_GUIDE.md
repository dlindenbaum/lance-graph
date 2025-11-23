# How to Specify Normalization Standards

## The Problem

In the original implementation, normalization was **implicit**:

```python
# ❌ Where is the normalization logic?
phone: Optional[str] = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.NORMALIZED  # How? What function?
    }
)

# ❌ Normalization hidden in validator
@field_validator('phone')
def validate_phone(cls, v):
    return re.sub(r'\D', '', v)  # Hardcoded!
```

**Problems:**
- Can't see normalization logic in schema
- Can't reuse normalization across entities
- Can't swap normalization strategies
- Hard to test in isolation

## The Solution: Explicit Normalization Functions

### Step 1: Create a Normalization Library

```python
class NormalizationFunctions:
    """Reusable normalization functions"""

    @staticmethod
    def phone_e164(value: Optional[str]) -> Optional[str]:
        """
        E.164 international format (digits only)

        Examples:
            "(555) 123-4567" → "5551234567"
            "+1-555-123-4567" → "15551234567"
        """
        if not value:
            return value
        return re.sub(r'\D', '', value)

    @staticmethod
    def phone_us_10digit(value: Optional[str]) -> Optional[str]:
        """
        US 10-digit format (strip country code)

        Examples:
            "+1-555-123-4567" → "5551234567"
            "1-555-123-4567" → "5551234567"
        """
        if not value:
            return value
        digits = re.sub(r'\D', '', value)
        # Strip leading 1 for US numbers
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        return digits

    @staticmethod
    def email_lowercase(value: Optional[str]) -> Optional[str]:
        """Lowercase email normalization"""
        return value.lower().strip() if value else value

    @staticmethod
    def email_gmail_normalize(value: Optional[str]) -> Optional[str]:
        """
        Gmail-specific normalization (dots and + ignored)

        Examples:
            "alice.smith@gmail.com" → "alicesmith@gmail.com"
            "alice+work@gmail.com" → "alice@gmail.com"
        """
        if not value or '@gmail.com' not in value.lower():
            return value.lower() if value else value

        local, domain = value.lower().split('@', 1)
        local = local.replace('.', '')  # Remove dots
        if '+' in local:
            local = local.split('+')[0]  # Remove + addressing

        return f"{local}@{domain}"

    @staticmethod
    def name_normalize(value: Optional[str]) -> Optional[str]:
        """
        Person name normalization

        Examples:
            "Dr. Alice M. Smith, PhD" → "alice m smith"
            "  Bob   Johnson  " → "bob johnson"
        """
        if not value:
            return value

        name = value.lower()
        # Remove titles
        name = re.sub(r'\b(mr|mrs|ms|dr|prof)\.?\s*', '', name)
        # Remove suffixes
        name = re.sub(r',?\s*(phd|md|jr|sr)\.?\s*$', '', name)
        # Remove punctuation
        name = re.sub(r'[^\w\s]', '', name)
        # Normalize whitespace
        return ' '.join(name.split())
```

### Step 2: Reference Functions in Field Metadata

```python
class PersonEntity(BaseModel):
    # Specify EXACTLY which normalization function to use
    phone: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.NORMALIZED,
            "normalization_fn": "phone_e164"  # ✅ EXPLICIT!
        }
    )

    email: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "normalization_fn": "email_lowercase"  # ✅ EXPLICIT!
        }
    )

    name: str = Field(
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "normalization_fn": "name_normalize"  # ✅ EXPLICIT!
        }
    )
```

### Step 3: Apply Normalization

```python
class PersonEntity(BaseModel):
    # ... fields ...

    @classmethod
    def normalize_field(cls, field_name: str, value: Any) -> Any:
        """Normalize a field using its specified function"""
        if value is None:
            return None

        metadata = cls.get_field_metadata(field_name)
        if metadata.normalization_fn:
            normalizer = getattr(NormalizationFunctions, metadata.normalization_fn)
            return normalizer(value)

        return value
```

## Usage Examples

### Example 1: Standard Phone Normalization

```python
class PersonEntity(BaseModel):
    phone: Optional[str] = Field(
        json_schema_extra={
            "normalization_fn": "phone_e164"  # International format
        }
    )

# Usage
PersonEntity.normalize_field("phone", "(555) 123-4567")
# Returns: "5551234567"

PersonEntity.normalize_field("phone", "+1-555-123-4567")
# Returns: "15551234567"
```

### Example 2: US-Specific Phone Normalization

```python
class USPersonEntity(BaseModel):
    phone: Optional[str] = Field(
        json_schema_extra={
            "normalization_fn": "phone_us_10digit"  # US format
        }
    )

# Usage
USPersonEntity.normalize_field("phone", "+1-555-123-4567")
# Returns: "5551234567" (country code stripped!)
```

### Example 3: Gmail-Aware Email Matching

```python
class GmailPersonEntity(BaseModel):
    email: Optional[str] = Field(
        json_schema_extra={
            "normalization_fn": "email_gmail_normalize"
        }
    )

# These all normalize to the same value!
GmailPersonEntity.normalize_field("email", "alice.smith@gmail.com")
# Returns: "alicesmith@gmail.com"

GmailPersonEntity.normalize_field("email", "alicesmith@gmail.com")
# Returns: "alicesmith@gmail.com"

GmailPersonEntity.normalize_field("email", "alice+work@gmail.com")
# Returns: "alice@gmail.com"

# So these would match as duplicates!
```

### Example 4: Different Entities, Different Standards

```python
# International company
class InternationalPersonEntity(BaseModel):
    phone: Optional[str] = Field(
        json_schema_extra={"normalization_fn": "phone_e164"}
    )

# US-only company
class USPersonEntity(BaseModel):
    phone: Optional[str] = Field(
        json_schema_extra={"normalization_fn": "phone_us_10digit"}
    )

# Same input, different normalization!
phone = "+1-555-123-4567"

InternationalPersonEntity.normalize_field("phone", phone)
# → "15551234567" (keep country code)

USPersonEntity.normalize_field("phone", phone)
# → "5551234567" (strip country code)
```

## Common Normalization Functions

### Phone Numbers

| Function | Use Case | Example |
|----------|----------|---------|
| `phone_e164` | International | "+1-555-123-4567" → "15551234567" |
| `phone_us_10digit` | US-only | "+1-555-123-4567" → "5551234567" |

### Email Addresses

| Function | Use Case | Example |
|----------|----------|---------|
| `email_lowercase` | Standard | "Alice@Example.COM" → "alice@example.com" |
| `email_gmail_normalize` | Gmail-specific | "alice.smith@gmail.com" → "alicesmith@gmail.com" |

### Names

| Function | Use Case | Example |
|----------|----------|---------|
| `name_normalize` | Standard | "Dr. Alice M. Smith, PhD" → "alice m smith" |
| `name_soundex` | Phonetic | "Smith" → "S530", "Smyth" → "S530" |

### Identifiers

| Function | Use Case | Example |
|----------|----------|---------|
| `ssn_normalize` | SSN | "123-45-6789" → "123456789" |
| `url_normalize` | URLs | "https://www.linkedin.com/" → "linkedin.com" |

### Addresses

| Function | Use Case | Example |
|----------|----------|---------|
| `address_normalize` | Street addresses | "123 Main Street, Apt 4" → "123 main st apt 4" |

## Complete Example

```python
from pydantic import BaseModel, Field

class PersonEntity(BaseModel):
    """Person with explicit normalization for each field"""

    entity_id: str

    # Phone: E.164 international format
    phone: Optional[str] = Field(
        default=None,
        description="Phone number (international format)",
        json_schema_extra={
            "match_strategy": MatchStrategy.NORMALIZED,
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0,
            "normalization_fn": "phone_e164"  # ← EXPLICIT
        }
    )

    # Email: Lowercase
    email: Optional[str] = Field(
        default=None,
        description="Email address",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0,
            "normalization_fn": "email_lowercase"  # ← EXPLICIT
        }
    )

    # Name: Remove titles, normalize spacing
    name: str = Field(
        description="Full name",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_LONGER,
            "match_weight": 2.0,
            "similarity_threshold": 0.8,
            "normalization_fn": "name_normalize"  # ← EXPLICIT
        }
    )

    # SSN: Digits only
    ssn: Optional[str] = Field(
        default=None,
        description="Social Security Number",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 10.0,
            "normalization_fn": "ssn_normalize"  # ← EXPLICIT
        }
    )

    # LinkedIn: Normalize URL
    linkedin: Optional[str] = Field(
        default=None,
        description="LinkedIn profile",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 5.0,
            "normalization_fn": "url_normalize"  # ← EXPLICIT
        }
    )

    # Address: Abbreviations, lowercase
    address: Optional[str] = Field(
        default=None,
        description="Street address",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_NON_NULL,
            "match_weight": 1.0,
            "similarity_threshold": 0.7,
            "normalization_fn": "address_normalize"  # ← EXPLICIT
        }
    )
```

## Creating Custom Normalization Functions

### Step 1: Add to NormalizationFunctions

```python
class NormalizationFunctions:
    # ... existing functions ...

    @staticmethod
    def my_custom_normalizer(value: Optional[str]) -> Optional[str]:
        """
        Custom normalization logic

        Examples:
            "input" → "output"
        """
        if not value:
            return value

        # Your custom logic here
        normalized = value.lower().strip()
        # ... more processing ...

        return normalized
```

### Step 2: Reference It

```python
class MyEntity(BaseModel):
    my_field: Optional[str] = Field(
        json_schema_extra={
            "normalization_fn": "my_custom_normalizer"  # Use it!
        }
    )
```

### Step 3: Test It

```python
def test_my_normalizer():
    result = NormalizationFunctions.my_custom_normalizer("TEST INPUT")
    assert result == "expected output"

def test_field_normalization():
    result = MyEntity.normalize_field("my_field", "TEST INPUT")
    assert result == "expected output"
```

## Best Practices

### 1. Document Your Normalization

```python
@staticmethod
def phone_e164(value: Optional[str]) -> Optional[str]:
    """
    E.164 international phone format

    Rules:
    - Remove all non-digits
    - Keep country code
    - No max length enforcement

    Examples:
        "(555) 123-4567" → "5551234567"
        "+1-555-123-4567" → "15551234567"

    References:
        https://en.wikipedia.org/wiki/E.164
    """
    if not value:
        return value
    return re.sub(r'\D', '', value)
```

### 2. Handle None Gracefully

```python
# ✅ Good
@staticmethod
def normalize_something(value: Optional[str]) -> Optional[str]:
    if not value:
        return value  # Don't crash on None
    return value.lower()

# ❌ Bad
@staticmethod
def normalize_something(value: str) -> str:
    return value.lower()  # Will crash if value is None!
```

### 3. Keep Functions Pure

```python
# ✅ Good (pure function, no side effects)
@staticmethod
def normalize_name(value: str) -> str:
    return value.lower()

# ❌ Bad (side effects, not reusable)
class MyNormalizer:
    def __init__(self):
        self.count = 0

    def normalize(self, value: str) -> str:
        self.count += 1  # Side effect!
        return value.lower()
```

### 4. Test in Isolation

```python
def test_phone_normalization():
    """Test normalization function directly"""
    assert NormalizationFunctions.phone_e164("(555) 123-4567") == "5551234567"
    assert NormalizationFunctions.phone_e164("+1-555-123-4567") == "15551234567"
    assert NormalizationFunctions.phone_e164(None) is None
```

### 5. Make Functions Reusable

```python
# ✅ Good - Generic, reusable
@staticmethod
def remove_punctuation(value: str) -> str:
    """Remove all punctuation"""
    return re.sub(r'[^\w\s]', '', value)

# ❌ Bad - Too specific, not reusable
@staticmethod
def normalize_john_smith(value: str) -> str:
    """Only works for 'John Smith'"""
    if value == "John Smith":
        return "john smith"
    return value
```

## Schema Inspection

You can inspect normalization at runtime:

```python
# See what normalization a field uses
metadata = PersonEntity.get_field_metadata("phone")
print(f"Normalization function: {metadata.normalization_fn}")
# Output: "phone_e164"

# Get the actual function
normalizer = metadata.get_normalizer()
print(normalizer)
# Output: <function NormalizationFunctions.phone_e164>

# Use it
result = normalizer("(555) 123-4567")
print(result)
# Output: "5551234567"
```

## Comparison: Before vs After

### Before (Implicit)

```python
# ❌ Can't see what normalization is used
phone: Optional[str] = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.NORMALIZED
    }
)

# ❌ Hidden in validator
@field_validator('phone')
def validate_phone(cls, v):
    return re.sub(r'\D', '', v)  # What is this doing?
```

**Problems:**
- Normalization logic is hidden
- Can't easily swap strategies
- Hard to test
- Can't reuse across entities

### After (Explicit)

```python
# ✅ Crystal clear what normalization is used
phone: Optional[str] = Field(
    json_schema_extra={
        "match_strategy": MatchStrategy.NORMALIZED,
        "normalization_fn": "phone_e164"  # ← See exactly what it does!
    }
)

# ✅ Logic is documented and reusable
class NormalizationFunctions:
    @staticmethod
    def phone_e164(value: Optional[str]) -> Optional[str]:
        """E.164 international format (digits only)"""
        if not value:
            return value
        return re.sub(r'\D', '', value)
```

**Benefits:**
- ✅ Explicit in schema
- ✅ Easy to swap (just change function name)
- ✅ Easy to test (direct function call)
- ✅ Reusable across all entities

## Run the Demo

```bash
python examples/pydantic_normalization_strategies.py
```

This shows:
- ✅ All available normalization functions
- ✅ Field configurations with explicit normalization
- ✅ Normalization in action (before/after examples)
- ✅ Gmail-specific normalization
- ✅ Different entity types with different standards
- ✅ Phonetic matching with Soundex

## Summary

**The key is making normalization functions EXPLICIT in your schema:**

```python
# Old way: ❌ Hidden
"match_strategy": MatchStrategy.NORMALIZED

# New way: ✅ Explicit
"match_strategy": MatchStrategy.NORMALIZED,
"normalization_fn": "phone_e164"  # You know exactly what happens!
```

This makes your entity resolution system:
- **Self-documenting** - Schema shows everything
- **Flexible** - Swap normalization by changing one field
- **Testable** - Test normalization in isolation
- **Maintainable** - Clear what each field does
- **Reusable** - Share functions across entities

**You now have complete control over how each field is normalized!** 🎉
