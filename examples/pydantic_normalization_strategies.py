"""
Enhanced Pydantic Entity Resolution with Explicit Normalization Functions

This version makes normalization strategies explicit and configurable in the schema,
so you can see EXACTLY how each field is normalized.
"""

from typing import Optional, List, Callable, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import re


# ============================================================================
# Normalization Functions (Explicit and Reusable)
# ============================================================================

class NormalizationFunctions:
    """
    Library of normalization functions

    Each function should be pure (no side effects) and handle None gracefully
    """

    @staticmethod
    def phone_e164(value: Optional[str]) -> Optional[str]:
        """
        Normalize phone to E.164 format (digits only)

        Examples:
            "(555) 123-4567" → "5551234567"
            "+1-555-123-4567" → "15551234567"
            "555.123.4567" → "5551234567"
        """
        if not value:
            return value
        return re.sub(r'\D', '', value)

    @staticmethod
    def phone_us_10digit(value: Optional[str]) -> Optional[str]:
        """
        Normalize US phone to 10 digits (strip country code)

        Examples:
            "+1-555-123-4567" → "5551234567"
            "1-555-123-4567" → "5551234567"
            "(555) 123-4567" → "5551234567"
        """
        if not value:
            return value
        digits = re.sub(r'\D', '', value)
        # Strip leading 1 for US numbers
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        return digits if len(digits) == 10 else digits

    @staticmethod
    def email_lowercase(value: Optional[str]) -> Optional[str]:
        """
        Normalize email to lowercase

        Examples:
            "Alice.Smith@Example.COM" → "alice.smith@example.com"
        """
        if not value:
            return value
        return value.lower().strip()

    @staticmethod
    def email_gmail_normalize(value: Optional[str]) -> Optional[str]:
        """
        Normalize Gmail addresses (dots and + ignored)

        Examples:
            "alice.smith@gmail.com" → "alicesmith@gmail.com"
            "alice+work@gmail.com" → "alice@gmail.com"
        """
        if not value:
            return value

        email = value.lower().strip()
        if '@gmail.com' not in email:
            return email

        local, domain = email.split('@', 1)
        # Remove dots
        local = local.replace('.', '')
        # Remove everything after +
        if '+' in local:
            local = local.split('+')[0]

        return f"{local}@{domain}"

    @staticmethod
    def name_normalize(value: Optional[str]) -> Optional[str]:
        """
        Normalize person name

        Examples:
            "  Alice   M.  Smith  " → "alice m smith"
            "Dr. Alice Smith" → "alice smith"
            "Alice M. Smith, PhD" → "alice m smith phd"
        """
        if not value:
            return value

        # Lowercase
        name = value.lower()

        # Remove common titles
        name = re.sub(r'\b(mr|mrs|ms|dr|prof|sr|jr)\.?\s*', '', name)

        # Remove common suffixes
        name = re.sub(r',?\s*(phd|md|esq|iii|iv|jr|sr)\.?\s*$', '', name)

        # Remove punctuation except spaces
        name = re.sub(r'[^\w\s]', '', name)

        # Normalize whitespace
        name = ' '.join(name.split())

        return name

    @staticmethod
    def name_soundex(value: Optional[str]) -> Optional[str]:
        """
        Soundex encoding for phonetic matching

        Examples:
            "Smith" → "S530"
            "Smyth" → "S530"  (same code!)
        """
        if not value:
            return value

        # Simple Soundex implementation
        value = value.upper()

        # Keep first letter
        soundex = value[0]

        # Mapping
        mapping = {
            'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3',
            'L': '4', 'MN': '5', 'R': '6'
        }

        for char in value[1:]:
            for key, code in mapping.items():
                if char in key:
                    if soundex[-1] != code:
                        soundex += code
                    break

        # Pad or trim to 4 characters
        soundex = (soundex + '000')[:4]
        return soundex

    @staticmethod
    def ssn_normalize(value: Optional[str]) -> Optional[str]:
        """
        Normalize SSN to digits only

        Examples:
            "123-45-6789" → "123456789"
            "123 45 6789" → "123456789"
        """
        if not value:
            return value
        return re.sub(r'\D', '', value)

    @staticmethod
    def url_normalize(value: Optional[str]) -> Optional[str]:
        """
        Normalize URL (remove protocol, www, trailing slash)

        Examples:
            "https://www.example.com/" → "example.com"
            "http://example.com/page" → "example.com/page"
        """
        if not value:
            return value

        # Remove protocol
        url = re.sub(r'^https?://', '', value.lower())

        # Remove www
        url = re.sub(r'^www\.', '', url)

        # Remove trailing slash
        url = url.rstrip('/')

        return url

    @staticmethod
    def address_normalize(value: Optional[str]) -> Optional[str]:
        """
        Normalize street address

        Examples:
            "123 Main Street, Apt 4" → "123 main st apt 4"
            "456 Oak Ave." → "456 oak ave"
        """
        if not value:
            return value

        address = value.lower()

        # Common abbreviations
        replacements = {
            r'\bstreet\b': 'st',
            r'\bavenue\b': 'ave',
            r'\broad\b': 'rd',
            r'\bdrive\b': 'dr',
            r'\blane\b': 'ln',
            r'\bapartment\b': 'apt',
            r'\bsuite\b': 'ste',
        }

        for pattern, replacement in replacements.items():
            address = re.sub(pattern, replacement, address)

        # Remove punctuation
        address = re.sub(r'[^\w\s]', '', address)

        # Normalize whitespace
        address = ' '.join(address.split())

        return address


# ============================================================================
# Enhanced Field Metadata with Normalization
# ============================================================================

class MatchStrategy(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    IGNORE = "ignore"


class MergeStrategy(str, Enum):
    KEEP = "keep"
    PREFER_NON_NULL = "prefer_non_null"
    PREFER_LONGER = "prefer_longer"
    CONCATENATE = "concatenate"


class FieldMetadata(BaseModel):
    """Enhanced metadata with explicit normalization function"""
    match_strategy: MatchStrategy
    merge_strategy: MergeStrategy
    match_weight: float = 1.0
    is_blocker: bool = False
    similarity_threshold: float = 0.8

    # NEW: Explicit normalization function name
    normalization_fn: Optional[str] = None

    def get_normalizer(self) -> Optional[Callable]:
        """Get the actual normalization function"""
        if not self.normalization_fn:
            return None

        # Look up function by name
        return getattr(NormalizationFunctions, self.normalization_fn, None)


# ============================================================================
# Enhanced Person Entity with Explicit Normalization
# ============================================================================

class PersonEntity(BaseModel):
    """
    Person entity with EXPLICIT normalization strategies

    Each field that uses NORMALIZED matching must specify which
    normalization function to use.
    """

    entity_id: str

    # Email with explicit normalization
    email: Optional[str] = Field(
        default=None,
        description="Email address",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0,
            # EXPLICIT: Use lowercase normalization for emails
            "normalization_fn": "email_lowercase"
        }
    )

    # Phone with explicit normalization
    phone: Optional[str] = Field(
        default=None,
        description="Phone number",
        json_schema_extra={
            "match_strategy": MatchStrategy.NORMALIZED,
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0,
            # EXPLICIT: Use E.164 normalization for phones
            "normalization_fn": "phone_e164"
        }
    )

    # Name with explicit normalization
    name: str = Field(
        description="Full name",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_LONGER,
            "match_weight": 2.0,
            "similarity_threshold": 0.8,
            # EXPLICIT: Use name normalization for fuzzy matching
            "normalization_fn": "name_normalize"
        }
    )

    # SSN with explicit normalization
    ssn: Optional[str] = Field(
        default=None,
        description="Social Security Number",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 10.0,
            # EXPLICIT: Normalize to digits only
            "normalization_fn": "ssn_normalize"
        }
    )

    # LinkedIn with explicit normalization
    linkedin: Optional[str] = Field(
        default=None,
        description="LinkedIn profile URL",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 5.0,
            # EXPLICIT: Normalize URL
            "normalization_fn": "url_normalize"
        }
    )

    # Address with explicit normalization
    address: Optional[str] = Field(
        default=None,
        description="Street address",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_NON_NULL,
            "match_weight": 1.0,
            "similarity_threshold": 0.7,
            # EXPLICIT: Normalize addresses
            "normalization_fn": "address_normalize"
        }
    )

    @classmethod
    def get_field_metadata(cls, field_name: str) -> FieldMetadata:
        """Get metadata for a field"""
        field_info = cls.model_fields.get(field_name)
        if not field_info:
            raise ValueError(f"Field {field_name} not found")

        extra = field_info.json_schema_extra or {}
        return FieldMetadata(**extra)

    @classmethod
    def normalize_field(cls, field_name: str, value: Any) -> Any:
        """
        Normalize a field value using its specified normalization function

        This is the key method that applies normalization!
        """
        if value is None:
            return None

        metadata = cls.get_field_metadata(field_name)
        normalizer = metadata.get_normalizer()

        if normalizer:
            return normalizer(value)

        return value


# ============================================================================
# Alternative: Gmail-Specific Person Entity
# ============================================================================

class GmailAwarePersonEntity(PersonEntity):
    """
    Person entity that uses Gmail-specific email normalization

    This handles Gmail's dots and + addressing quirks
    """

    email: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.NORMALIZED,
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0,
            # Different normalization for Gmail
            "normalization_fn": "email_gmail_normalize"
        }
    )


# ============================================================================
# Alternative: US-Specific Person Entity
# ============================================================================

class USPersonEntity(PersonEntity):
    """Person entity with US-specific phone normalization"""

    phone: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.NORMALIZED,
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0,
            # US-specific: strip country code, 10 digits only
            "normalization_fn": "phone_us_10digit"
        }
    )


# ============================================================================
# Demo
# ============================================================================

def demo():
    """Demonstrate explicit normalization"""

    print("="*80)
    print("Explicit Normalization Strategies Demo")
    print("="*80)

    # Show what normalization functions are available
    print("\n📚 Available Normalization Functions:")
    print("\nPhone:")
    print("  • phone_e164: Digits only (international)")
    print("  • phone_us_10digit: 10 digits (strip country code)")

    print("\nEmail:")
    print("  • email_lowercase: Lowercase only")
    print("  • email_gmail_normalize: Gmail dots/+ handling")

    print("\nName:")
    print("  • name_normalize: Remove titles, normalize spacing")
    print("  • name_soundex: Phonetic encoding")

    print("\nOther:")
    print("  • ssn_normalize: Digits only")
    print("  • url_normalize: Remove protocol, www")
    print("  • address_normalize: Abbreviations, lowercase")

    # Show field metadata
    print("\n" + "="*80)
    print("PersonEntity Schema (with normalization functions)")
    print("="*80)

    print("\n📋 Field Configurations:")
    for field_name in ["email", "phone", "name", "ssn", "linkedin", "address"]:
        metadata = PersonEntity.get_field_metadata(field_name)
        print(f"\n{field_name}:")
        print(f"  Match strategy: {metadata.match_strategy.value}")
        print(f"  Normalization: {metadata.normalization_fn or 'None'}")
        print(f"  Is blocker: {metadata.is_blocker}")
        print(f"  Weight: {metadata.match_weight}")

    # Test normalization
    print("\n" + "="*80)
    print("Normalization in Action")
    print("="*80)

    test_cases = [
        ("phone", "(555) 123-4567"),
        ("phone", "+1-555-123-4567"),
        ("phone", "555.123.4567"),
        ("email", "Alice.Smith@Example.COM"),
        ("name", "Dr. Alice M. Smith, PhD"),
        ("name", "  Bob   Johnson  "),
        ("ssn", "123-45-6789"),
        ("linkedin", "https://www.linkedin.com/in/alice-smith/"),
        ("address", "123 Main Street, Apt 4"),
    ]

    print("\nNormalizing various inputs:")
    for field, value in test_cases:
        normalized = PersonEntity.normalize_field(field, value)
        print(f"\n{field}:")
        print(f"  Input:  '{value}'")
        print(f"  Output: '{normalized}'")

    # Test Gmail normalization
    print("\n" + "="*80)
    print("Gmail-Specific Normalization")
    print("="*80)

    print("\nStandard email normalization:")
    print(f"  alice.smith@gmail.com → {PersonEntity.normalize_field('email', 'alice.smith@gmail.com')}")

    print("\nGmail-aware normalization:")
    gmail_cases = [
        "alice.smith@gmail.com",
        "alicesmith@gmail.com",  # Same after normalization!
        "alice+work@gmail.com",
    ]

    for email in gmail_cases:
        normalized = NormalizationFunctions.email_gmail_normalize(email)
        print(f"  {email:30s} → {normalized}")

    # Test matching with normalization
    print("\n" + "="*80)
    print("Matching with Normalization")
    print("="*80)

    person1 = PersonEntity(
        entity_id="p1",
        name="Alice Smith",
        phone="5551234567",  # Already normalized
        email="alice@example.com"
    )

    person2_phones = [
        "(555) 123-4567",
        "+1-555-123-4567",
        "555.123.4567",
        "555-123-4567",
    ]

    print(f"\nPerson 1 phone (normalized): {person1.phone}")
    print("\nChecking if these phones match:")

    for phone in person2_phones:
        normalized = PersonEntity.normalize_field('phone', phone)
        matches = normalized == person1.phone
        symbol = "✅" if matches else "❌"
        print(f"  {symbol} '{phone}' → '{normalized}' (match: {matches})")

    # Different entity types, different normalization
    print("\n" + "="*80)
    print("Different Entity Types = Different Normalization")
    print("="*80)

    print("\nStandard PersonEntity (international phone):")
    phone_test = "+1-555-123-4567"
    norm1 = PersonEntity.normalize_field('phone', phone_test)
    print(f"  {phone_test} → {norm1}")

    print("\nUSPersonEntity (US-specific, strip country code):")
    norm2 = USPersonEntity.normalize_field('phone', phone_test)
    print(f"  {phone_test} → {norm2}")

    # Soundex example
    print("\n" + "="*80)
    print("Phonetic Matching with Soundex")
    print("="*80)

    names = ["Smith", "Smyth", "Schmidt", "Smitty"]
    print("\nThese names sound similar:")
    for name in names:
        soundex = NormalizationFunctions.name_soundex(name)
        print(f"  {name:10s} → {soundex}")

    print("\n✅ Smith and Smyth have the same Soundex code!")
    print("   → Could use this for fuzzy name matching")

    # Summary
    print("\n" + "="*80)
    print("Key Benefits")
    print("="*80)

    print("""
✅ EXPLICIT: Each field shows exactly how it's normalized
✅ REUSABLE: Normalization functions can be shared across entities
✅ FLEXIBLE: Different entities can use different normalizations
✅ TESTABLE: Easy to test normalization in isolation
✅ DOCUMENTED: Schema shows everything in one place

To add a new normalization:
1. Add function to NormalizationFunctions
2. Reference it in field's json_schema_extra
3. That's it! The resolver automatically uses it.
    """)


if __name__ == "__main__":
    demo()
