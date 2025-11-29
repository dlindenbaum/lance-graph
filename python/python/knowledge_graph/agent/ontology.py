"""Ontology definition and validation for graph construction."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


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
