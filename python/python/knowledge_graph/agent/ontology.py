"""Ontology definition and validation for graph construction."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class MatchStrategy(str, Enum):
    """Strategy for matching entities."""

    EXACT = "exact"  # Exact match required
    FUZZY = "fuzzy"  # Fuzzy string matching
    NORMALIZED = "normalized"  # Normalized comparison (lowercase, strip spaces)
    SEMANTIC = "semantic"  # Semantic similarity


class MatchingRule(BaseModel):
    """Rule for matching entities of the same type."""

    properties: List[str] = Field(..., description="Properties to match on")
    strategy: MatchStrategy = Field(
        default=MatchStrategy.NORMALIZED, description="Matching strategy"
    )
    confidence_threshold: float = Field(
        default=0.8,
        description="Minimum confidence for a match (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    weight: float = Field(
        default=1.0, description="Weight of this rule in overall matching", ge=0.0
    )


class MergeStrategy(BaseModel):
    """Strategy for merging matched entities."""

    prefer_higher_confidence: bool = Field(
        default=True, description="Prefer properties from higher confidence source"
    )
    combine_properties: bool = Field(
        default=True, description="Combine properties from both entities"
    )
    require_manual_review: bool = Field(
        default=True, description="Require manual review before merging"
    )


class EntityType(BaseModel):
    """Definition of an entity type in the ontology."""

    name: str = Field(..., description="Entity type name (e.g., Person, Location, Vehicle)")
    description: Optional[str] = Field(None, description="Description of this entity type")
    required_properties: List[str] = Field(
        default_factory=list, description="Properties that must be present"
    )
    optional_properties: List[str] = Field(
        default_factory=list, description="Properties that may be present"
    )
    property_types: Dict[str, str] = Field(
        default_factory=dict, description="Expected types for properties (str, int, float, date, etc.)"
    )
    identifier_properties: List[str] = Field(
        default_factory=list, description="Properties that uniquely identify this entity"
    )
    matching_rules: List[MatchingRule] = Field(
        default_factory=list, description="Rules for matching entities of this type"
    )
    merge_strategy: Optional[MergeStrategy] = Field(
        None, description="Strategy for merging matched entities"
    )


class RelationshipType(BaseModel):
    """Definition of a relationship type in the ontology."""

    name: str = Field(..., description="Relationship type name (e.g., KNOWS, LOCATED_AT, OWNS)")
    description: Optional[str] = Field(None, description="Description of this relationship")
    source_entity_types: List[str] = Field(
        ..., description="Valid source entity types"
    )
    target_entity_types: List[str] = Field(
        ..., description="Valid target entity types"
    )
    properties: List[str] = Field(
        default_factory=list, description="Properties that can be on this relationship"
    )
    directional: bool = Field(
        default=True, description="Whether the relationship is directional"
    )


class GraphOntology(BaseModel):
    """Complete ontology definition for a knowledge graph domain."""

    name: str = Field(..., description="Ontology name (e.g., 'Transportation', 'Telecommunications')")
    description: Optional[str] = Field(None, description="Description of this ontology")
    entity_types: List[EntityType] = Field(default_factory=list)
    relationship_types: List[RelationshipType] = Field(default_factory=list)

    def get_entity_type(self, name: str) -> Optional[EntityType]:
        """Get entity type by name."""
        for et in self.entity_types:
            if et.name.lower() == name.lower():
                return et
        return None

    def get_relationship_type(self, name: str) -> Optional[RelationshipType]:
        """Get relationship type by name."""
        for rt in self.relationship_types:
            if rt.name.lower() == name.lower():
                return rt
        return None

    def validate_entity(
        self, entity_type: str, properties: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """Validate an entity against the ontology.

        Returns:
            (is_valid, list_of_errors)
        """
        et = self.get_entity_type(entity_type)
        if not et:
            return False, [f"Unknown entity type: {entity_type}"]

        errors = []

        # Check required properties
        for prop in et.required_properties:
            if prop not in properties:
                errors.append(f"Missing required property: {prop}")

        # Check property types if defined
        for prop, value in properties.items():
            if prop in et.property_types:
                expected_type = et.property_types[prop]
                if not self._check_type(value, expected_type):
                    errors.append(
                        f"Property {prop} has wrong type. Expected {expected_type}, got {type(value).__name__}"
                    )

        return len(errors) == 0, errors

    def validate_relationship(
        self,
        relationship_type: str,
        source_entity_type: str,
        target_entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, List[str]]:
        """Validate a relationship against the ontology.

        Returns:
            (is_valid, list_of_errors)
        """
        rt = self.get_relationship_type(relationship_type)
        if not rt:
            return False, [f"Unknown relationship type: {relationship_type}"]

        errors = []

        # Check source entity type
        if source_entity_type not in rt.source_entity_types:
            errors.append(
                f"Invalid source entity type. Expected one of {rt.source_entity_types}, got {source_entity_type}"
            )

        # Check target entity type
        if target_entity_type not in rt.target_entity_types:
            errors.append(
                f"Invalid target entity type. Expected one of {rt.target_entity_types}, got {target_entity_type}"
            )

        return len(errors) == 0, errors

    def get_valid_entity_types(self) -> List[str]:
        """Get list of all valid entity type names."""
        return [et.name for et in self.entity_types]

    def get_valid_relationship_types(self) -> List[str]:
        """Get list of all valid relationship type names."""
        return [rt.name for rt in self.relationship_types]

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "str": str,
            "int": int,
            "float": (int, float),
            "bool": bool,
            "date": str,  # Simplified, could parse
            "datetime": str,
        }

        expected = type_map.get(expected_type.lower())
        if expected is None:
            return True  # Unknown type, skip validation

        return isinstance(value, expected)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "GraphOntology":
        """Load ontology from YAML file."""
        import yaml
        from pathlib import Path

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    def to_yaml(self, yaml_path: str) -> None:
        """Save ontology to YAML file."""
        import yaml
        from pathlib import Path

        with open(yaml_path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)

    @classmethod
    def combine(cls, *ontologies: "GraphOntology", name: Optional[str] = None) -> "GraphOntology":
        """Combine multiple ontologies into one.

        Args:
            *ontologies: Variable number of ontologies to combine
            name: Name for the combined ontology (default: concatenated names)

        Returns:
            Combined ontology with all entity types and relationships
        """
        if not ontologies:
            raise ValueError("At least one ontology must be provided")

        # Collect all entity types and relationship types
        entity_types_dict: Dict[str, EntityType] = {}
        relationship_types_dict: Dict[str, RelationshipType] = {}

        combined_descriptions = []

        for ontology in ontologies:
            if ontology.description:
                combined_descriptions.append(ontology.description)

            # Add entity types (avoid duplicates by name)
            for et in ontology.entity_types:
                if et.name not in entity_types_dict:
                    entity_types_dict[et.name] = et
                else:
                    # Merge properties if entity type already exists
                    existing = entity_types_dict[et.name]
                    # Combine optional properties
                    all_optional = set(existing.optional_properties) | set(et.optional_properties)
                    existing.optional_properties = list(all_optional)
                    # Combine property types
                    existing.property_types.update(et.property_types)

            # Add relationship types (avoid duplicates by name and entity types)
            for rt in ontology.relationship_types:
                key = f"{rt.name}_{','.join(sorted(rt.source_entity_types))}_{','.join(sorted(rt.target_entity_types))}"
                if key not in relationship_types_dict:
                    relationship_types_dict[key] = rt

        combined_name = name or " + ".join(ont.name for ont in ontologies)
        combined_description = " | ".join(combined_descriptions) if combined_descriptions else None

        return cls(
            name=combined_name,
            description=combined_description,
            entity_types=list(entity_types_dict.values()),
            relationship_types=list(relationship_types_dict.values()),
        )

    def match_entities(
        self,
        entity_type: str,
        entity1_props: Dict[str, Any],
        entity2_props: Dict[str, Any],
    ) -> tuple[bool, float, List[str]]:
        """Check if two entities match based on ontology rules.

        Args:
            entity_type: Type of entities to match
            entity1_props: Properties of first entity
            entity2_props: Properties of second entity

        Returns:
            (is_match, confidence, matched_rules)
        """
        et = self.get_entity_type(entity_type)
        if not et or not et.matching_rules:
            return False, 0.0, []

        total_weight = sum(rule.weight for rule in et.matching_rules)
        if total_weight == 0:
            return False, 0.0, []

        matched_rules = []
        weighted_confidence = 0.0

        for rule in et.matching_rules:
            match_score = self._evaluate_matching_rule(
                rule, entity1_props, entity2_props
            )

            if match_score >= rule.confidence_threshold:
                matched_rules.append(
                    f"{','.join(rule.properties)} ({rule.strategy.value})"
                )
                weighted_confidence += match_score * rule.weight

        overall_confidence = weighted_confidence / total_weight
        is_match = len(matched_rules) > 0

        return is_match, overall_confidence, matched_rules

    def _evaluate_matching_rule(
        self,
        rule: MatchingRule,
        props1: Dict[str, Any],
        props2: Dict[str, Any],
    ) -> float:
        """Evaluate a single matching rule.

        Returns:
            Confidence score (0.0-1.0)
        """
        # Check if all properties exist in both entities
        for prop in rule.properties:
            if prop not in props1 or prop not in props2:
                return 0.0

        # Get values to compare
        values1 = [props1.get(prop) for prop in rule.properties]
        values2 = [props2.get(prop) for prop in rule.properties]

        # Compare based on strategy
        if rule.strategy == MatchStrategy.EXACT:
            matches = sum(1 for v1, v2 in zip(values1, values2) if v1 == v2)
            return matches / len(values1)

        elif rule.strategy == MatchStrategy.NORMALIZED:
            matches = 0
            for v1, v2 in zip(values1, values2):
                if v1 is None or v2 is None:
                    continue
                norm1 = str(v1).lower().strip()
                norm2 = str(v2).lower().strip()
                if norm1 == norm2:
                    matches += 1
            return matches / len(values1) if values1 else 0.0

        elif rule.strategy == MatchStrategy.FUZZY:
            # Simple fuzzy matching using string similarity
            try:
                from difflib import SequenceMatcher

                total_similarity = 0.0
                for v1, v2 in zip(values1, values2):
                    if v1 is None or v2 is None:
                        continue
                    s1, s2 = str(v1), str(v2)
                    similarity = SequenceMatcher(None, s1, s2).ratio()
                    total_similarity += similarity
                return total_similarity / len(values1) if values1 else 0.0
            except Exception:
                return 0.0

        elif rule.strategy == MatchStrategy.SEMANTIC:
            # Semantic matching would require embeddings - fallback to fuzzy for now
            return self._evaluate_matching_rule(
                MatchingRule(
                    properties=rule.properties,
                    strategy=MatchStrategy.FUZZY,
                    confidence_threshold=rule.confidence_threshold,
                    weight=rule.weight,
                ),
                props1,
                props2,
            )

        return 0.0


# Predefined ontology templates
class OntologyTemplates:
    """Common ontology templates for different domains."""

    @staticmethod
    def generic() -> GraphOntology:
        """Generic ontology that accepts any entity/relationship."""
        return GraphOntology(
            name="Generic",
            description="Generic ontology for exploratory analysis",
            entity_types=[
                EntityType(
                    name="Entity",
                    description="Generic entity type",
                    required_properties=[],
                    optional_properties=[],
                )
            ],
            relationship_types=[
                RelationshipType(
                    name="RELATED",
                    description="Generic relationship",
                    source_entity_types=["Entity"],
                    target_entity_types=["Entity"],
                )
            ],
        )

    @staticmethod
    def telecommunications() -> GraphOntology:
        """Ontology for telecommunications/CDR data."""
        return GraphOntology(
            name="Telecommunications",
            description="Ontology for call data records and telecommunications",
            entity_types=[
                EntityType(
                    name="Person",
                    description="Individual person",
                    required_properties=["name"],
                    optional_properties=["email", "address", "date_of_birth"],
                    identifier_properties=["person_id", "ssn"],
                ),
                EntityType(
                    name="Phone",
                    description="Phone number",
                    required_properties=["number"],
                    optional_properties=["carrier", "type", "status"],
                    identifier_properties=["number"],
                    property_types={"number": "str", "carrier": "str"},
                ),
                EntityType(
                    name="Location",
                    description="Physical location",
                    required_properties=["name"],
                    optional_properties=["address", "city", "state", "coordinates"],
                    identifier_properties=["location_id"],
                ),
            ],
            relationship_types=[
                RelationshipType(
                    name="CONTACTED",
                    description="Phone call or message between phones",
                    source_entity_types=["Phone"],
                    target_entity_types=["Phone"],
                    properties=["timestamp", "duration", "call_type"],
                ),
                RelationshipType(
                    name="OWNS",
                    description="Person owns a phone",
                    source_entity_types=["Person"],
                    target_entity_types=["Phone"],
                    properties=["since_date"],
                ),
                RelationshipType(
                    name="LOCATED_AT",
                    description="Entity at location",
                    source_entity_types=["Phone", "Person"],
                    target_entity_types=["Location"],
                    properties=["timestamp", "confidence"],
                ),
            ],
        )

    @staticmethod
    def transportation() -> GraphOntology:
        """Ontology for transportation/taxi data."""
        return GraphOntology(
            name="Transportation",
            description="Ontology for transportation and vehicle tracking",
            entity_types=[
                EntityType(
                    name="Driver",
                    description="Vehicle driver",
                    required_properties=["driver_id", "name"],
                    optional_properties=["license_number", "hire_date", "rating"],
                    identifier_properties=["driver_id", "license_number"],
                ),
                EntityType(
                    name="Vehicle",
                    description="Vehicle",
                    required_properties=["vehicle_id"],
                    optional_properties=["make", "model", "year", "license_plate"],
                    identifier_properties=["vehicle_id", "license_plate"],
                ),
                EntityType(
                    name="Location",
                    description="Geographic location",
                    required_properties=["name"],
                    optional_properties=["latitude", "longitude", "address"],
                    identifier_properties=["location_id"],
                ),
                EntityType(
                    name="Passenger",
                    description="Passenger",
                    required_properties=["passenger_id"],
                    optional_properties=["name", "phone", "rating"],
                    identifier_properties=["passenger_id"],
                ),
            ],
            relationship_types=[
                RelationshipType(
                    name="DROVE",
                    description="Driver drove vehicle",
                    source_entity_types=["Driver"],
                    target_entity_types=["Vehicle"],
                    properties=["start_time", "end_time"],
                ),
                RelationshipType(
                    name="TRIP",
                    description="Trip from one location to another",
                    source_entity_types=["Location"],
                    target_entity_types=["Location"],
                    properties=["timestamp", "distance", "duration", "fare"],
                ),
                RelationshipType(
                    name="PICKED_UP",
                    description="Driver picked up passenger",
                    source_entity_types=["Driver"],
                    target_entity_types=["Passenger"],
                    properties=["timestamp", "location"],
                ),
            ],
        )

    @staticmethod
    def financial() -> GraphOntology:
        """Ontology for financial transactions."""
        return GraphOntology(
            name="Financial",
            description="Ontology for financial transactions and accounts",
            entity_types=[
                EntityType(
                    name="Account",
                    description="Financial account",
                    required_properties=["account_id"],
                    optional_properties=["account_type", "balance", "status"],
                    identifier_properties=["account_id"],
                ),
                EntityType(
                    name="Person",
                    description="Account holder",
                    required_properties=["person_id", "name"],
                    optional_properties=["ssn", "address", "date_of_birth"],
                    identifier_properties=["person_id", "ssn"],
                ),
                EntityType(
                    name="Merchant",
                    description="Merchant or vendor",
                    required_properties=["merchant_id", "name"],
                    optional_properties=["category", "location"],
                    identifier_properties=["merchant_id"],
                ),
            ],
            relationship_types=[
                RelationshipType(
                    name="OWNS",
                    description="Person owns account",
                    source_entity_types=["Person"],
                    target_entity_types=["Account"],
                    properties=["since_date", "role"],
                ),
                RelationshipType(
                    name="TRANSACTION",
                    description="Transaction between accounts",
                    source_entity_types=["Account"],
                    target_entity_types=["Account", "Merchant"],
                    properties=["amount", "timestamp", "transaction_type"],
                ),
            ],
        )

    @staticmethod
    def communication() -> GraphOntology:
        """Ontology for communication analysis (pattern of life).

        Covers: phone calls, text messages, emails, in-person meetings.
        Focus: Establishing communication patterns and social networks.
        """
        return GraphOntology(
            name="Communication",
            description="Communication patterns for pattern-of-life analysis",
            entity_types=[
                EntityType(
                    name="Person",
                    description="Individual in the communication network",
                    required_properties=["name"],
                    optional_properties=["email", "phone", "address", "role", "organization"],
                    identifier_properties=["person_id", "ssn", "employee_id"],
                    property_types={"name": "str", "email": "str", "phone": "str"},
                    matching_rules=[
                        MatchingRule(
                            properties=["person_id"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["ssn"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["email"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.95,
                            weight=8.0,
                        ),
                        MatchingRule(
                            properties=["phone"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.95,
                            weight=8.0,
                        ),
                        MatchingRule(
                            properties=["name"],
                            strategy=MatchStrategy.FUZZY,
                            confidence_threshold=0.85,
                            weight=5.0,
                        ),
                        MatchingRule(
                            properties=["name", "address"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.9,
                            weight=7.0,
                        ),
                    ],
                    merge_strategy=MergeStrategy(
                        prefer_higher_confidence=True,
                        combine_properties=True,
                        require_manual_review=True,
                    ),
                ),
                EntityType(
                    name="Phone",
                    description="Phone number or device",
                    required_properties=["number"],
                    optional_properties=["carrier", "type", "device_id", "imei"],
                    identifier_properties=["number", "device_id", "imei"],
                    property_types={"number": "str", "carrier": "str", "type": "str"},
                    matching_rules=[
                        MatchingRule(
                            properties=["number"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.95,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["device_id"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["imei"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                    ],
                    merge_strategy=MergeStrategy(
                        prefer_higher_confidence=True,
                        combine_properties=True,
                        require_manual_review=False,
                    ),
                ),
                EntityType(
                    name="EmailAddress",
                    description="Email address",
                    required_properties=["address"],
                    optional_properties=["domain", "verified", "type"],
                    identifier_properties=["address"],
                    property_types={"address": "str", "domain": "str", "verified": "bool"},
                ),
                EntityType(
                    name="MeetingLocation",
                    description="Physical location where meetings occur",
                    required_properties=["name"],
                    optional_properties=["address", "coordinates", "type"],
                    identifier_properties=["location_id"],
                    property_types={"name": "str", "address": "str", "type": "str"},
                ),
            ],
            relationship_types=[
                RelationshipType(
                    name="CALLED",
                    description="Phone call between parties",
                    source_entity_types=["Person", "Phone"],
                    target_entity_types=["Person", "Phone"],
                    properties=["timestamp", "duration", "direction", "call_type"],
                    directional=True,
                ),
                RelationshipType(
                    name="TEXTED",
                    description="Text/SMS message",
                    source_entity_types=["Person", "Phone"],
                    target_entity_types=["Person", "Phone"],
                    properties=["timestamp", "message_count", "direction"],
                    directional=True,
                ),
                RelationshipType(
                    name="EMAILED",
                    description="Email communication",
                    source_entity_types=["Person", "EmailAddress"],
                    target_entity_types=["Person", "EmailAddress"],
                    properties=["timestamp", "subject", "cc_count", "has_attachment"],
                    directional=True,
                ),
                RelationshipType(
                    name="MET_IN_PERSON",
                    description="In-person meeting or encounter",
                    source_entity_types=["Person"],
                    target_entity_types=["Person"],
                    properties=["timestamp", "duration", "location", "witnesses"],
                    directional=False,
                ),
                RelationshipType(
                    name="OWNS",
                    description="Person owns communication device",
                    source_entity_types=["Person"],
                    target_entity_types=["Phone", "EmailAddress"],
                    properties=["since_date", "verified", "confidence"],
                    directional=True,
                ),
                RelationshipType(
                    name="MET_AT",
                    description="Meeting occurred at location",
                    source_entity_types=["Person"],
                    target_entity_types=["MeetingLocation"],
                    properties=["timestamp", "duration", "purpose", "attendees"],
                    directional=False,
                ),
            ],
        )

    @staticmethod
    def location() -> GraphOntology:
        """Ontology for location analysis (pattern of life).

        Covers: home, work, third places, meeting locations, movement patterns.
        Focus: Establishing location patterns and spatial relationships.
        """
        return GraphOntology(
            name="Location",
            description="Location and movement patterns for pattern-of-life analysis",
            entity_types=[
                EntityType(
                    name="Person",
                    description="Individual whose location is tracked",
                    required_properties=["name"],
                    optional_properties=["home_address", "work_address", "vehicle_id"],
                    identifier_properties=["person_id"],
                    property_types={"name": "str"},
                    matching_rules=[
                        MatchingRule(
                            properties=["person_id"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["name", "home_address"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.9,
                            weight=9.0,
                        ),
                        MatchingRule(
                            properties=["name", "work_address"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.9,
                            weight=9.0,
                        ),
                        MatchingRule(
                            properties=["name"],
                            strategy=MatchStrategy.FUZZY,
                            confidence_threshold=0.85,
                            weight=5.0,
                        ),
                    ],
                    merge_strategy=MergeStrategy(
                        prefer_higher_confidence=True,
                        combine_properties=True,
                        require_manual_review=True,
                    ),
                ),
                EntityType(
                    name="Home",
                    description="Residential location",
                    required_properties=["address"],
                    optional_properties=["coordinates", "residence_type", "occupants"],
                    identifier_properties=["location_id", "address"],
                    property_types={"address": "str", "residence_type": "str"},
                    matching_rules=[
                        MatchingRule(
                            properties=["location_id"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["address"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.9,
                            weight=9.0,
                        ),
                    ],
                    merge_strategy=MergeStrategy(
                        prefer_higher_confidence=True,
                        combine_properties=True,
                        require_manual_review=False,
                    ),
                ),
                EntityType(
                    name="Work",
                    description="Workplace or business location",
                    required_properties=["name", "address"],
                    optional_properties=["coordinates", "business_type", "hours"],
                    identifier_properties=["location_id", "business_id"],
                    property_types={"name": "str", "address": "str"},
                    matching_rules=[
                        MatchingRule(
                            properties=["location_id"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["business_id"],
                            strategy=MatchStrategy.EXACT,
                            confidence_threshold=1.0,
                            weight=10.0,
                        ),
                        MatchingRule(
                            properties=["name", "address"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.9,
                            weight=9.0,
                        ),
                        MatchingRule(
                            properties=["address"],
                            strategy=MatchStrategy.NORMALIZED,
                            confidence_threshold=0.85,
                            weight=7.0,
                        ),
                    ],
                    merge_strategy=MergeStrategy(
                        prefer_higher_confidence=True,
                        combine_properties=True,
                        require_manual_review=False,
                    ),
                ),
                EntityType(
                    name="ThirdPlace",
                    description="Regular location that is neither home nor work (cafes, gyms, etc.)",
                    required_properties=["name"],
                    optional_properties=["address", "coordinates", "category", "frequency"],
                    identifier_properties=["location_id"],
                    property_types={"name": "str", "category": "str", "frequency": "str"},
                ),
                EntityType(
                    name="MeetingLocation",
                    description="Location where meetings or gatherings occur",
                    required_properties=["name"],
                    optional_properties=["address", "coordinates", "type", "capacity"],
                    identifier_properties=["location_id"],
                    property_types={"name": "str", "type": "str"},
                ),
                EntityType(
                    name="Vehicle",
                    description="Vehicle used for transportation",
                    required_properties=["vehicle_id"],
                    optional_properties=["make", "model", "color", "license_plate"],
                    identifier_properties=["vehicle_id", "license_plate"],
                    property_types={"license_plate": "str"},
                ),
            ],
            relationship_types=[
                RelationshipType(
                    name="LIVES_AT",
                    description="Person resides at location",
                    source_entity_types=["Person"],
                    target_entity_types=["Home"],
                    properties=["since_date", "confidence", "verified"],
                    directional=True,
                ),
                RelationshipType(
                    name="WORKS_AT",
                    description="Person employed at location",
                    source_entity_types=["Person"],
                    target_entity_types=["Work"],
                    properties=["since_date", "job_title", "schedule", "verified"],
                    directional=True,
                ),
                RelationshipType(
                    name="FREQUENTS",
                    description="Person regularly visits location",
                    source_entity_types=["Person"],
                    target_entity_types=["ThirdPlace"],
                    properties=["visit_count", "typical_days", "typical_times", "average_duration"],
                    directional=True,
                ),
                RelationshipType(
                    name="VISITED",
                    description="Person visited location at specific time",
                    source_entity_types=["Person"],
                    target_entity_types=["Home", "Work", "ThirdPlace", "MeetingLocation"],
                    properties=["timestamp", "duration", "purpose", "confidence"],
                    directional=True,
                ),
                RelationshipType(
                    name="TRAVELED",
                    description="Movement from one location to another",
                    source_entity_types=["Home", "Work", "ThirdPlace", "MeetingLocation"],
                    target_entity_types=["Home", "Work", "ThirdPlace", "MeetingLocation"],
                    properties=["timestamp", "duration", "distance", "mode_of_transport"],
                    directional=True,
                ),
                RelationshipType(
                    name="OWNS_VEHICLE",
                    description="Person owns or operates vehicle",
                    source_entity_types=["Person"],
                    target_entity_types=["Vehicle"],
                    properties=["since_date", "ownership_type", "verified"],
                    directional=True,
                ),
                RelationshipType(
                    name="PARKED_AT",
                    description="Vehicle parked at location",
                    source_entity_types=["Vehicle"],
                    target_entity_types=["Home", "Work", "ThirdPlace", "MeetingLocation"],
                    properties=["timestamp", "duration"],
                    directional=False,
                ),
                RelationshipType(
                    name="CO_LOCATED",
                    description="Multiple people at same location at same time",
                    source_entity_types=["Person"],
                    target_entity_types=["Person"],
                    properties=["timestamp", "location", "duration", "confidence"],
                    directional=False,
                ),
            ],
        )

    @staticmethod
    def temporal() -> GraphOntology:
        """Ontology for temporal pattern analysis (pattern of life).

        Covers: time patterns, routines, schedules, anomalies.
        Focus: Establishing temporal patterns and behavioral rhythms.
        """
        return GraphOntology(
            name="Temporal",
            description="Temporal patterns and routines for pattern-of-life analysis",
            entity_types=[
                EntityType(
                    name="Person",
                    description="Individual whose temporal patterns are analyzed",
                    required_properties=["name"],
                    optional_properties=["timezone", "work_schedule"],
                    identifier_properties=["person_id"],
                    property_types={"name": "str", "timezone": "str"},
                ),
                EntityType(
                    name="TimePattern",
                    description="Recurring temporal pattern or routine",
                    required_properties=["pattern_name", "pattern_type"],
                    optional_properties=["frequency", "time_of_day", "days_of_week", "confidence"],
                    identifier_properties=["pattern_id"],
                    property_types={"pattern_name": "str", "pattern_type": "str", "frequency": "str"},
                ),
                EntityType(
                    name="Event",
                    description="Discrete event or activity",
                    required_properties=["event_type", "timestamp"],
                    optional_properties=["duration", "location", "participants"],
                    identifier_properties=["event_id"],
                    property_types={"event_type": "str", "timestamp": "datetime", "duration": "int"},
                ),
                EntityType(
                    name="Routine",
                    description="Established routine or habit",
                    required_properties=["routine_name"],
                    optional_properties=["description", "start_time", "end_time", "frequency", "regularity_score"],
                    identifier_properties=["routine_id"],
                    property_types={"routine_name": "str", "start_time": "str", "end_time": "str"},
                ),
                EntityType(
                    name="Anomaly",
                    description="Deviation from normal pattern",
                    required_properties=["anomaly_type", "timestamp"],
                    optional_properties=["severity", "description", "baseline_pattern"],
                    identifier_properties=["anomaly_id"],
                    property_types={"anomaly_type": "str", "timestamp": "datetime", "severity": "str"},
                ),
            ],
            relationship_types=[
                RelationshipType(
                    name="HAS_PATTERN",
                    description="Person exhibits temporal pattern",
                    source_entity_types=["Person"],
                    target_entity_types=["TimePattern"],
                    properties=["discovered_date", "confidence", "sample_size"],
                    directional=True,
                ),
                RelationshipType(
                    name="FOLLOWS_ROUTINE",
                    description="Person follows routine",
                    source_entity_types=["Person"],
                    target_entity_types=["Routine"],
                    properties=["adherence_rate", "since_date", "last_observed"],
                    directional=True,
                ),
                RelationshipType(
                    name="PERFORMED",
                    description="Person performed event",
                    source_entity_types=["Person"],
                    target_entity_types=["Event"],
                    properties=["timestamp", "confidence"],
                    directional=True,
                ),
                RelationshipType(
                    name="PART_OF_PATTERN",
                    description="Event is part of pattern",
                    source_entity_types=["Event"],
                    target_entity_types=["TimePattern", "Routine"],
                    properties=["fit_score", "frequency"],
                    directional=True,
                ),
                RelationshipType(
                    name="PRECEDES",
                    description="One event typically precedes another",
                    source_entity_types=["Event"],
                    target_entity_types=["Event"],
                    properties=["typical_interval", "confidence", "observed_count"],
                    directional=True,
                ),
                RelationshipType(
                    name="DEVIATES_FROM",
                    description="Anomaly deviates from normal pattern",
                    source_entity_types=["Anomaly"],
                    target_entity_types=["TimePattern", "Routine"],
                    properties=["deviation_magnitude", "timestamp"],
                    directional=True,
                ),
                RelationshipType(
                    name="EXHIBITED_ANOMALY",
                    description="Person exhibited anomalous behavior",
                    source_entity_types=["Person"],
                    target_entity_types=["Anomaly"],
                    properties=["timestamp", "investigated"],
                    directional=True,
                ),
                RelationshipType(
                    name="CO_OCCURS",
                    description="Events that frequently occur together",
                    source_entity_types=["Event"],
                    target_entity_types=["Event"],
                    properties=["co_occurrence_rate", "typical_time_delta"],
                    directional=False,
                ),
            ],
        )

    @staticmethod
    def pattern_of_life() -> GraphOntology:
        """Combined ontology for comprehensive pattern-of-life analysis.

        Combines: Communication + Location + Temporal ontologies.
        Use this for full-spectrum pattern-of-life investigations.
        """
        return GraphOntology.combine(
            OntologyTemplates.communication(),
            OntologyTemplates.location(),
            OntologyTemplates.temporal(),
            name="Pattern of Life",
        )
