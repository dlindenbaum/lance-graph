"""
Pydantic-Based Entity Resolution

Uses Pydantic models to explicitly define:
- Which fields are used for exact vs fuzzy matching
- Merge strategies per field
- Confidence thresholds
- Validation rules

Benefits:
- Type safety
- Self-documenting code
- Easy to update matching logic
- JSON schema generation
- Validation at runtime
"""

from typing import Optional, List, Literal, Dict, Any, Set
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
from dataclasses import dataclass
import re


# ============================================================================
# Field Matching Strategy Definitions
# ============================================================================

class MatchStrategy(str, Enum):
    """How to match this field"""
    EXACT = "exact"              # Must match exactly (email, SSN, ID)
    NORMALIZED = "normalized"     # Match after normalization (phone, name)
    FUZZY = "fuzzy"              # Similarity-based (name, address)
    SEMANTIC = "semantic"         # Embedding-based
    IGNORE = "ignore"            # Don't use for matching


class MergeStrategy(str, Enum):
    """How to merge this field when combining duplicates"""
    KEEP = "keep"                # Keep value from canonical entity
    PREFER_NON_NULL = "prefer_non_null"  # Fill in missing values
    PREFER_LONGER = "prefer_longer"      # Keep longer string
    PREFER_NEWER = "prefer_newer"        # Use most recent value
    CONCATENATE = "concatenate"          # Combine all unique values
    TAKE_MAX = "take_max"               # Take maximum value
    TAKE_MIN = "take_min"               # Take minimum value


class FieldMetadata(BaseModel):
    """Metadata about how to match and merge a field"""
    match_strategy: MatchStrategy = MatchStrategy.IGNORE
    merge_strategy: MergeStrategy = MergeStrategy.KEEP
    match_weight: float = Field(default=1.0, ge=0.0, le=10.0)
    is_blocker: bool = False  # If True, exact match = immediate link
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Entity Schema Definitions
# ============================================================================

class PersonEntity(BaseModel):
    """
    Person entity with explicit matching/merging strategies per field

    Each field includes metadata that defines:
    - How to match it (exact, fuzzy, semantic, ignore)
    - How to merge it when combining duplicates
    - Match weight (importance in scoring)
    - Whether it's a blocker (immediate match)
    """

    # Core identity fields
    entity_id: str = Field(
        description="Unique identifier",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 10.0
        }
    )

    name: str = Field(
        description="Full name",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_LONGER,
            "match_weight": 2.0,
            "similarity_threshold": 0.8
        }
    )

    # Strong identifiers (blockers)
    email: Optional[str] = Field(
        default=None,
        description="Email address - blocker field",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.CONCATENATE,  # Keep all emails
            "is_blocker": True,
            "match_weight": 5.0
        }
    )

    phone: Optional[str] = Field(
        default=None,
        description="Phone number - normalized matching",
        json_schema_extra={
            "match_strategy": MatchStrategy.NORMALIZED,
            "merge_strategy": MergeStrategy.CONCATENATE,
            "is_blocker": True,
            "match_weight": 5.0
        }
    )

    linkedin: Optional[str] = Field(
        default=None,
        description="LinkedIn profile URL - blocker field",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 5.0
        }
    )

    ssn: Optional[str] = Field(
        default=None,
        description="Social Security Number - strongest blocker",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 10.0
        }
    )

    # Supporting fields
    date_of_birth: Optional[str] = Field(
        default=None,
        description="Date of birth",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.PREFER_NON_NULL,
            "match_weight": 3.0
        }
    )

    address: Optional[str] = Field(
        default=None,
        description="Current address - fuzzy match",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_NEWER,
            "match_weight": 1.0,
            "similarity_threshold": 0.7
        }
    )

    # Metadata fields
    context: Optional[str] = Field(
        default=None,
        description="Additional context",
        json_schema_extra={
            "match_strategy": MatchStrategy.IGNORE,
            "merge_strategy": MergeStrategy.CONCATENATE
        }
    )

    created_at: Optional[str] = Field(
        default=None,
        description="Record creation timestamp",
        json_schema_extra={
            "match_strategy": MatchStrategy.IGNORE,
            "merge_strategy": MergeStrategy.TAKE_MIN
        }
    )

    updated_at: Optional[str] = Field(
        default=None,
        description="Last update timestamp",
        json_schema_extra={
            "match_strategy": MatchStrategy.IGNORE,
            "merge_strategy": MergeStrategy.TAKE_MAX
        }
    )

    # Validators
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v and '@' not in v:
            raise ValueError("Invalid email format")
        return v.lower() if v else v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v:
            # Store normalized for easy matching
            return re.sub(r'\D', '', v)
        return v

    @classmethod
    def get_field_metadata(cls, field_name: str) -> FieldMetadata:
        """Get matching/merging metadata for a field"""
        field_info = cls.model_fields.get(field_name)
        if not field_info:
            raise ValueError(f"Field {field_name} not found")

        extra = field_info.json_schema_extra or {}
        return FieldMetadata(
            match_strategy=extra.get('match_strategy', MatchStrategy.IGNORE),
            merge_strategy=extra.get('merge_strategy', MergeStrategy.KEEP),
            match_weight=extra.get('match_weight', 1.0),
            is_blocker=extra.get('is_blocker', False),
            similarity_threshold=extra.get('similarity_threshold', 0.8)
        )

    @classmethod
    def get_blocker_fields(cls) -> List[str]:
        """Get all fields marked as blockers"""
        blockers = []
        for field_name in cls.model_fields:
            metadata = cls.get_field_metadata(field_name)
            if metadata.is_blocker:
                blockers.append(field_name)
        return blockers

    @classmethod
    def get_fuzzy_fields(cls) -> List[str]:
        """Get all fields using fuzzy matching"""
        fuzzy = []
        for field_name in cls.model_fields:
            metadata = cls.get_field_metadata(field_name)
            if metadata.match_strategy == MatchStrategy.FUZZY:
                fuzzy.append(field_name)
        return fuzzy


class OrganizationEntity(BaseModel):
    """Organization entity with matching strategies"""

    entity_id: str = Field(
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 10.0
        }
    )

    name: str = Field(
        description="Company name",
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_LONGER,
            "match_weight": 3.0,
            "similarity_threshold": 0.85
        }
    )

    domain: Optional[str] = Field(
        default=None,
        description="Website domain (e.g., 'google.com')",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 5.0
        }
    )

    tax_id: Optional[str] = Field(
        default=None,
        description="Tax ID / EIN",
        json_schema_extra={
            "match_strategy": MatchStrategy.EXACT,
            "merge_strategy": MergeStrategy.KEEP,
            "is_blocker": True,
            "match_weight": 10.0
        }
    )

    address: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "match_strategy": MatchStrategy.FUZZY,
            "merge_strategy": MergeStrategy.PREFER_NON_NULL,
            "match_weight": 1.0
        }
    )


# ============================================================================
# Resolution Configuration
# ============================================================================

class ResolutionConfig(BaseModel):
    """
    Configuration for entity resolution thresholds and behavior
    """

    # Confidence thresholds
    auto_merge_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Auto-merge if confidence >= this threshold"
    )

    review_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Flag for review if confidence >= this threshold"
    )

    # Blocker behavior
    blocker_exact_match_weight: float = Field(
        default=2.0,
        description="Weight multiplier for exact blocker matches"
    )

    # Fuzzy matching
    min_name_similarity: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum name similarity to consider as candidate"
    )

    # Merge behavior
    auto_merge_enabled: bool = Field(
        default=True,
        description="Allow automatic merging of high-confidence matches"
    )

    preserve_all_values: bool = Field(
        default=False,
        description="If True, keep all unique values in merged fields"
    )


# ============================================================================
# Resolution Results
# ============================================================================

class MatchReason(BaseModel):
    """Detailed reason for a match"""
    field: str
    strategy: MatchStrategy
    confidence: float
    details: str


class ResolutionDecision(BaseModel):
    """Decision about what to do with incoming entity"""

    action: Literal["create_new", "merge_with", "needs_review"]
    confidence: float = Field(ge=0.0, le=1.0)
    matched_entity_id: Optional[str] = None
    match_reasons: List[MatchReason] = Field(default_factory=list)

    def add_reason(self, field: str, strategy: MatchStrategy,
                   confidence: float, details: str):
        """Add a match reason"""
        self.match_reasons.append(MatchReason(
            field=field,
            strategy=strategy,
            confidence=confidence,
            details=details
        ))


class MergeResult(BaseModel):
    """Result of merging entities"""

    canonical_entity_id: str
    merged_entity_ids: List[str]
    merged_entity: Dict[str, Any]
    field_merge_log: Dict[str, str]  # field -> how it was merged

    def describe(self) -> str:
        """Human-readable description"""
        lines = [
            f"Merged {len(self.merged_entity_ids)} entities into {self.canonical_entity_id}",
            "\nField merge details:"
        ]
        for field, strategy in self.field_merge_log.items():
            lines.append(f"  • {field}: {strategy}")
        return "\n".join(lines)


# ============================================================================
# Pydantic-Driven Resolver
# ============================================================================

class PydanticEntityResolver:
    """
    Entity resolver that uses Pydantic model metadata to drive matching
    """

    def __init__(
        self,
        entity_class: type[BaseModel],
        config: ResolutionConfig = ResolutionConfig()
    ):
        self.entity_class = entity_class
        self.config = config

        # Extract metadata once
        self.blocker_fields = self._get_blocker_fields()
        self.fuzzy_fields = self._get_fuzzy_fields()
        self.field_metadata = self._extract_field_metadata()

    def _get_blocker_fields(self) -> List[str]:
        """Get all blocker fields from model"""
        if hasattr(self.entity_class, 'get_blocker_fields'):
            return self.entity_class.get_blocker_fields()
        return []

    def _get_fuzzy_fields(self) -> List[str]:
        """Get all fuzzy match fields from model"""
        if hasattr(self.entity_class, 'get_fuzzy_fields'):
            return self.entity_class.get_fuzzy_fields()
        return []

    def _extract_field_metadata(self) -> Dict[str, FieldMetadata]:
        """Extract all field metadata from model"""
        metadata = {}
        for field_name in self.entity_class.model_fields:
            if hasattr(self.entity_class, 'get_field_metadata'):
                metadata[field_name] = self.entity_class.get_field_metadata(field_name)
        return metadata

    def should_merge(
        self,
        candidate: BaseModel,
        existing: BaseModel
    ) -> ResolutionDecision:
        """
        Determine if candidate should merge with existing entity

        Uses Pydantic model metadata to drive the decision
        """
        decision = ResolutionDecision(
            action="create_new",
            confidence=0.0,
            matched_entity_id=existing.entity_id
        )

        total_weight = 0.0
        weighted_score = 0.0

        # Step 1: Check blocker fields (exact matches)
        for field_name in self.blocker_fields:
            metadata = self.field_metadata.get(field_name)
            if not metadata:
                continue

            candidate_value = getattr(candidate, field_name, None)
            existing_value = getattr(existing, field_name, None)

            # Skip if either is None
            if candidate_value is None or existing_value is None:
                continue

            # Check match based on strategy
            if metadata.match_strategy == MatchStrategy.EXACT:
                if candidate_value == existing_value:
                    # Blocker match! High confidence
                    score = 1.0
                    weight = metadata.match_weight * self.config.blocker_exact_match_weight

                    decision.add_reason(
                        field=field_name,
                        strategy=MatchStrategy.EXACT,
                        confidence=1.0,
                        details=f"Exact match on blocker field: {candidate_value}"
                    )

                    weighted_score += score * weight
                    total_weight += weight

        # Step 2: Check fuzzy fields
        for field_name in self.fuzzy_fields:
            metadata = self.field_metadata.get(field_name)
            if not metadata:
                continue

            candidate_value = getattr(candidate, field_name, None)
            existing_value = getattr(existing, field_name, None)

            if candidate_value is None or existing_value is None:
                continue

            # Calculate similarity
            similarity = self._calculate_similarity(
                str(candidate_value),
                str(existing_value),
                metadata.match_strategy
            )

            if similarity >= metadata.similarity_threshold:
                decision.add_reason(
                    field=field_name,
                    strategy=metadata.match_strategy,
                    confidence=similarity,
                    details=f"Similarity: {similarity:.2%}"
                )

                weighted_score += similarity * metadata.match_weight
                total_weight += metadata.match_weight

        # Calculate final confidence
        if total_weight > 0:
            decision.confidence = weighted_score / total_weight

        # Determine action based on thresholds
        if decision.confidence >= self.config.auto_merge_threshold:
            decision.action = "merge_with"
        elif decision.confidence >= self.config.review_threshold:
            decision.action = "needs_review"
        else:
            decision.action = "create_new"

        return decision

    def merge_entities(
        self,
        canonical: BaseModel,
        duplicates: List[BaseModel]
    ) -> MergeResult:
        """
        Merge duplicate entities into canonical using Pydantic metadata
        """
        merged_data = canonical.model_dump()
        field_merge_log = {}

        # Process each field according to its merge strategy
        for field_name, metadata in self.field_metadata.items():
            values = [getattr(canonical, field_name)]

            # Collect all values from duplicates
            for dup in duplicates:
                value = getattr(dup, field_name, None)
                if value is not None:
                    values.append(value)

            # Apply merge strategy
            merged_value = self._apply_merge_strategy(
                values,
                metadata.merge_strategy
            )

            merged_data[field_name] = merged_value
            field_merge_log[field_name] = metadata.merge_strategy.value

        return MergeResult(
            canonical_entity_id=canonical.entity_id,
            merged_entity_ids=[d.entity_id for d in duplicates],
            merged_entity=merged_data,
            field_merge_log=field_merge_log
        )

    def _calculate_similarity(
        self,
        value1: str,
        value2: str,
        strategy: MatchStrategy
    ) -> float:
        """Calculate similarity based on strategy"""
        if strategy == MatchStrategy.EXACT:
            return 1.0 if value1 == value2 else 0.0

        elif strategy == MatchStrategy.NORMALIZED:
            norm1 = self._normalize_string(value1)
            norm2 = self._normalize_string(value2)
            return 1.0 if norm1 == norm2 else 0.0

        elif strategy == MatchStrategy.FUZZY:
            # Token overlap
            tokens1 = set(self._normalize_string(value1).split())
            tokens2 = set(self._normalize_string(value2).split())

            if not tokens1 or not tokens2:
                return 0.0

            overlap = len(tokens1 & tokens2)
            total = len(tokens1 | tokens2)

            return overlap / total if total > 0 else 0.0

        else:
            return 0.0

    def _normalize_string(self, s: str) -> str:
        """Normalize string for comparison"""
        s = s.lower()
        s = re.sub(r'[^\w\s]', '', s)
        return ' '.join(s.split())

    def _apply_merge_strategy(
        self,
        values: List[Any],
        strategy: MergeStrategy
    ) -> Any:
        """Apply merge strategy to list of values"""
        # Filter out None values
        non_null = [v for v in values if v is not None]

        if not non_null:
            return None

        if strategy == MergeStrategy.KEEP:
            return values[0]  # Keep first (canonical)

        elif strategy == MergeStrategy.PREFER_NON_NULL:
            return non_null[0]  # First non-null

        elif strategy == MergeStrategy.PREFER_LONGER:
            return max(non_null, key=lambda x: len(str(x)))

        elif strategy == MergeStrategy.CONCATENATE:
            # Return unique values as comma-separated
            unique = list(dict.fromkeys(str(v) for v in non_null))
            return ", ".join(unique)

        elif strategy == MergeStrategy.TAKE_MAX:
            return max(non_null)

        elif strategy == MergeStrategy.TAKE_MIN:
            return min(non_null)

        else:
            return values[0]


# ============================================================================
# Demo
# ============================================================================

def demo():
    """Demonstrate Pydantic-based entity resolution"""

    print("="*80)
    print("Pydantic-Based Entity Resolution")
    print("="*80)

    # Show the model schema
    print("\n📋 PersonEntity Schema:")
    print("\nBlocker fields (exact match = immediate link):")
    for field in PersonEntity.get_blocker_fields():
        metadata = PersonEntity.get_field_metadata(field)
        print(f"  • {field}: {metadata.match_strategy.value} "
              f"(weight: {metadata.match_weight})")

    print("\nFuzzy match fields:")
    for field in PersonEntity.get_fuzzy_fields():
        metadata = PersonEntity.get_field_metadata(field)
        print(f"  • {field}: threshold={metadata.similarity_threshold}")

    # Create test entities
    print("\n" + "="*80)
    print("Test Scenario: Matching Entities")
    print("="*80)

    existing = PersonEntity(
        entity_id="person_001",
        name="Alice Smith",
        email="alice.smith@techcorp.com",
        phone="5550123",  # Normalized
        linkedin="linkedin.com/in/alicesmith",
        date_of_birth="1990-01-15"
    )

    print("\n📊 Existing Entity:")
    print(f"  Name: {existing.name}")
    print(f"  Email: {existing.email}")
    print(f"  Phone: {existing.phone}")
    print(f"  LinkedIn: {existing.linkedin}")

    # Test Case 1: Exact email match
    print("\n" + "-"*80)
    print("Test 1: Exact Email Match")
    print("-"*80)

    candidate1 = PersonEntity(
        entity_id="person_temp_1",
        name="Alice M. Smith",  # Slightly different name
        email="alice.smith@techcorp.com",  # SAME
        phone="5559999",  # Different phone
        linkedin=None
    )

    print(f"\n📥 Candidate:")
    print(f"  Name: {candidate1.name}")
    print(f"  Email: {candidate1.email}")
    print(f"  Phone: {candidate1.phone}")

    resolver = PydanticEntityResolver(PersonEntity)
    decision1 = resolver.should_merge(candidate1, existing)

    print(f"\n✅ Decision: {decision1.action}")
    print(f"   Confidence: {decision1.confidence:.1%}")
    print(f"   Reasons:")
    for reason in decision1.match_reasons:
        print(f"     • {reason.field}: {reason.details}")

    # Test Case 2: Phone + fuzzy name (no email)
    print("\n" + "-"*80)
    print("Test 2: Phone Match + Fuzzy Name")
    print("-"*80)

    candidate2 = PersonEntity(
        entity_id="person_temp_2",
        name="Alice Smith",  # Same name
        email="alice@personal.com",  # Different email
        phone="5550123",  # SAME phone
        linkedin=None
    )

    print(f"\n📥 Candidate:")
    print(f"  Name: {candidate2.name}")
    print(f"  Email: {candidate2.email}")
    print(f"  Phone: {candidate2.phone}")

    decision2 = resolver.should_merge(candidate2, existing)

    print(f"\n✅ Decision: {decision2.action}")
    print(f"   Confidence: {decision2.confidence:.1%}")
    print(f"   Reasons:")
    for reason in decision2.match_reasons:
        print(f"     • {reason.field}: {reason.details}")

    # Test Case 3: Similar name only (ambiguous)
    print("\n" + "-"*80)
    print("Test 3: Similar Name Only (Needs Review)")
    print("-"*80)

    candidate3 = PersonEntity(
        entity_id="person_temp_3",
        name="Alicia Smith",  # Similar but not exact
        email="alicia@somewhere.com",
        phone="5559876",
        linkedin=None
    )

    print(f"\n📥 Candidate:")
    print(f"  Name: {candidate3.name}")
    print(f"  Email: {candidate3.email}")

    decision3 = resolver.should_merge(candidate3, existing)

    print(f"\n✅ Decision: {decision3.action}")
    print(f"   Confidence: {decision3.confidence:.1%}")
    print(f"   Reasons:")
    for reason in decision3.match_reasons:
        print(f"     • {reason.field}: {reason.details}")

    # Test Case 4: Merging entities
    print("\n" + "="*80)
    print("Test 4: Merging Entities")
    print("="*80)

    duplicate1 = PersonEntity(
        entity_id="person_dup_1",
        name="Alice M. Smith",  # Longer name
        email="alice@newco.com",
        phone="5550123",
        linkedin="linkedin.com/in/alicesmith",
        address="123 New Street"  # New info
    )

    duplicate2 = PersonEntity(
        entity_id="person_dup_2",
        name="Alice Smith",
        email="asmith@startup.com",
        phone="5550123",
        linkedin="linkedin.com/in/alicesmith",
        date_of_birth="1990-01-15"
    )

    print("\n📋 Merging 2 duplicates into canonical entity...")

    merge_result = resolver.merge_entities(existing, [duplicate1, duplicate2])

    print(f"\n{merge_result.describe()}")

    print("\n📊 Merged Entity:")
    for field, value in merge_result.merged_entity.items():
        if value and field not in ['entity_id', 'context']:
            print(f"  • {field}: {value}")

    # Show what changed
    print("\n🔄 What changed from canonical:")
    print(f"  • name: '{existing.name}' → '{merge_result.merged_entity['name']}' "
          f"(strategy: prefer_longer)")
    print(f"  • email: '{existing.email}' → '{merge_result.merged_entity['email']}' "
          f"(strategy: concatenate - all emails kept)")
    print(f"  • address: None → '{merge_result.merged_entity['address']}' "
          f"(strategy: prefer_non_null)")

    print("\n" + "="*80)
    print("Key Benefits of Pydantic Approach")
    print("="*80)
    print("""
✅ Self-documenting: Field metadata explains matching logic
✅ Type-safe: Pydantic validates at runtime
✅ Easy to update: Change metadata, logic updates automatically
✅ Testable: Clear schema makes unit testing easier
✅ JSON schema: Auto-generate API documentation
✅ IDE support: Autocomplete and type hints
✅ Flexible: Different strategies per entity type (Person vs Organization)
    """)


if __name__ == "__main__":
    demo()
