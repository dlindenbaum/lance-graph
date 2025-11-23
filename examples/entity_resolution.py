"""
Entity Resolution System for Lance-Graph

This script demonstrates how to build an entity resolution system that:
1. Ingests raw person/organization/event data
2. Identifies duplicate entities using multiple strategies
3. Suggests merges based on similarity scores
4. Handles cases like person contact info across company moves
"""

import pyarrow as pa
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import hashlib

from knowledge_graph import create_default_service, KnowledgeGraphService
from knowledge_graph.embeddings import EmbeddingGenerator, cosine_similarity


@dataclass
class EntityMatch:
    """Represents a potential duplicate entity match"""
    entity_id_1: str
    entity_id_2: str
    similarity_score: float
    match_reasons: List[str]
    shared_context: Dict[str, Any]


@dataclass
class RawContactRecord:
    """Raw data record for a person's contact information"""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    address: Optional[str] = None
    linkedin: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class EntityResolver:
    """
    Entity Resolution system for identifying and merging duplicate entities
    """

    def __init__(
        self,
        service: KnowledgeGraphService,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        similarity_threshold: float = 0.85
    ):
        self.service = service
        self.embedding_gen = embedding_generator or EmbeddingGenerator(
            model="text-embedding-3-small"
        )
        self.similarity_threshold = similarity_threshold

    def ingest_contact_records(self, records: List[RawContactRecord]) -> Dict[str, List[str]]:
        """
        Ingest raw contact records and create Person, Organization, and Employment nodes

        Returns:
            Dictionary mapping entity types to lists of created entity IDs
        """
        entities = []
        organizations = {}
        relationships = []

        for idx, record in enumerate(records):
            # Create Person entity
            person_id = self._generate_entity_id(f"person_{record.name}_{idx}")
            person_name = record.name

            # Create embedding for semantic matching
            # Combine name and contextual info for better matching
            context_text = f"{record.name}"
            if record.job_title:
                context_text += f" {record.job_title}"
            if record.email:
                context_text += f" {record.email}"

            embedding = self.embedding_gen.embed_one(context_text)

            # Normalize for exact matching
            name_normalized = self._normalize_name(person_name)
            email_normalized = record.email.lower() if record.email else None

            entities.append({
                "entity_id": person_id,
                "name": person_name,
                "entity_type": "PERSON",
                "context": f"Email: {record.email or 'N/A'}, Phone: {record.phone or 'N/A'}",
                "embedding": embedding,
                "name_lower": name_normalized,
                # Custom fields for resolution
                "email": record.email,
                "phone": record.phone,
                "linkedin": record.linkedin,
            })

            # Create Organization entity if company specified
            if record.company:
                org_id = self._get_or_create_organization(
                    record.company,
                    organizations
                )

                # Create WORKS_AT relationship
                relationships.append({
                    "source_entity_id": person_id,
                    "target_entity_id": org_id,
                    "relationship_type": "WORKS_AT",
                    "description": f"{record.job_title or 'Employee'} from {record.start_date or 'unknown'} to {record.end_date or 'present'}",
                    "job_title": record.job_title,
                    "start_date": record.start_date,
                    "end_date": record.end_date,
                })

        # Add organization entities
        entities.extend(organizations.values())

        # Write to knowledge graph
        entity_table = pa.Table.from_pylist(entities)
        self.service.upsert_table("Entity", entity_table)

        if relationships:
            rel_table = pa.Table.from_pylist(relationships)
            self.service.upsert_table("RELATIONSHIP", rel_table)

        # Return created IDs by type
        created_ids = defaultdict(list)
        for entity in entities:
            created_ids[entity["entity_type"]].append(entity["entity_id"])

        return dict(created_ids)

    def find_duplicate_candidates(
        self,
        entity_type: str = "PERSON",
        strategies: List[str] = None
    ) -> List[EntityMatch]:
        """
        Find potential duplicate entities using multiple strategies

        Strategies:
        - exact_email: Exact match on email addresses
        - exact_phone: Exact match on phone numbers
        - exact_linkedin: Exact match on LinkedIn profiles
        - fuzzy_name: Normalized name matching
        - semantic: Embedding-based semantic similarity
        - graph_context: Shared relationships and context

        Returns:
            List of EntityMatch objects sorted by similarity score
        """
        if strategies is None:
            strategies = ["exact_email", "fuzzy_name", "semantic", "graph_context"]

        # Load all entities of the specified type
        query = f"MATCH (e:Entity) WHERE e.entity_type = '{entity_type}' RETURN e"
        result = self.service.run(query)
        entities = []

        # Convert PyArrow table to list of dicts
        for i in range(result.num_rows):
            entity = {}
            for column in result.column_names:
                entity[column] = result[column][i].as_py()
            entities.append(entity)

        matches = []
        seen_pairs = set()

        # Compare all pairs of entities
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                pair_key = tuple(sorted([entity1["entity_id"], entity2["entity_id"]]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Apply each strategy
                match_reasons = []
                scores = []
                shared_context = {}

                # Strategy 1: Exact email match
                if "exact_email" in strategies:
                    if entity1.get("email") and entity2.get("email"):
                        if entity1["email"] == entity2["email"]:
                            match_reasons.append("exact_email")
                            scores.append(1.0)
                            shared_context["email"] = entity1["email"]

                # Strategy 2: Exact phone match
                if "exact_phone" in strategies:
                    if entity1.get("phone") and entity2.get("phone"):
                        phone1 = self._normalize_phone(entity1["phone"])
                        phone2 = self._normalize_phone(entity2["phone"])
                        if phone1 == phone2:
                            match_reasons.append("exact_phone")
                            scores.append(1.0)
                            shared_context["phone"] = entity1["phone"]

                # Strategy 3: Exact LinkedIn match
                if "exact_linkedin" in strategies:
                    if entity1.get("linkedin") and entity2.get("linkedin"):
                        if entity1["linkedin"] == entity2["linkedin"]:
                            match_reasons.append("exact_linkedin")
                            scores.append(1.0)
                            shared_context["linkedin"] = entity1["linkedin"]

                # Strategy 4: Fuzzy name matching
                if "fuzzy_name" in strategies:
                    name_sim = self._name_similarity(
                        entity1["name"],
                        entity2["name"]
                    )
                    if name_sim > 0.8:
                        match_reasons.append(f"fuzzy_name_{name_sim:.2f}")
                        scores.append(name_sim)

                # Strategy 5: Semantic similarity using embeddings
                if "semantic" in strategies:
                    if "embedding" in entity1 and "embedding" in entity2:
                        sem_sim = cosine_similarity(
                            entity1["embedding"],
                            entity2["embedding"]
                        )
                        if sem_sim > self.similarity_threshold:
                            match_reasons.append(f"semantic_{sem_sim:.2f}")
                            scores.append(sem_sim)

                # Strategy 6: Graph context (shared relationships)
                if "graph_context" in strategies:
                    context_score = self._graph_context_similarity(
                        entity1["entity_id"],
                        entity2["entity_id"]
                    )
                    if context_score > 0:
                        match_reasons.append(f"shared_connections_{context_score:.2f}")
                        scores.append(context_score)
                        shared_context["connection_overlap"] = context_score

                # If any strategy found a match, create an EntityMatch
                if scores:
                    # Weighted average (exact matches weighted higher)
                    weights = [2.0 if "exact_" in reason else 1.0
                              for reason in match_reasons]
                    weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

                    matches.append(EntityMatch(
                        entity_id_1=entity1["entity_id"],
                        entity_id_2=entity2["entity_id"],
                        similarity_score=weighted_score,
                        match_reasons=match_reasons,
                        shared_context=shared_context
                    ))

        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches

    def get_merge_suggestions(
        self,
        min_confidence: float = 0.7,
        include_context: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get human-readable merge suggestions with full context

        Returns:
            List of merge suggestions with entity details and reasoning
        """
        matches = self.find_duplicate_candidates()
        suggestions = []

        for match in matches:
            if match.similarity_score < min_confidence:
                continue

            # Get full entity details
            entity1 = self._get_entity_details(match.entity_id_1)
            entity2 = self._get_entity_details(match.entity_id_2)

            suggestion = {
                "confidence": match.similarity_score,
                "match_reasons": match.match_reasons,
                "entity_1": {
                    "id": entity1["entity_id"],
                    "name": entity1["name"],
                    "email": entity1.get("email"),
                    "phone": entity1.get("phone"),
                },
                "entity_2": {
                    "id": entity2["entity_id"],
                    "name": entity2["name"],
                    "email": entity2.get("email"),
                    "phone": entity2.get("phone"),
                },
                "shared_context": match.shared_context,
            }

            # Include relationship context if requested
            if include_context:
                suggestion["entity_1"]["relationships"] = self._get_entity_relationships(
                    match.entity_id_1
                )
                suggestion["entity_2"]["relationships"] = self._get_entity_relationships(
                    match.entity_id_2
                )

            suggestions.append(suggestion)

        return suggestions

    def merge_entities(
        self,
        keep_id: str,
        merge_ids: List[str],
        merge_strategy: str = "prefer_keep"
    ) -> Dict[str, Any]:
        """
        Merge duplicate entities into a canonical entity

        Args:
            keep_id: The canonical entity ID to keep
            merge_ids: List of duplicate entity IDs to merge
            merge_strategy: How to merge properties
                - "prefer_keep": Keep existing values from keep_id
                - "prefer_complete": Use most complete data
                - "merge_all": Combine all unique values

        Returns:
            Dictionary with merge statistics
        """
        # Get all entities
        all_entities = self.service.load_table("Entity").to_pylist()

        # Find entities to merge
        keep_entity = None
        merge_entities = []
        other_entities = []

        for entity in all_entities:
            if entity["entity_id"] == keep_id:
                keep_entity = entity
            elif entity["entity_id"] in merge_ids:
                merge_entities.append(entity)
            else:
                other_entities.append(entity)

        if not keep_entity:
            raise ValueError(f"Keep entity {keep_id} not found")

        # Merge properties based on strategy
        merged_entity = self._merge_entity_properties(
            keep_entity,
            merge_entities,
            merge_strategy
        )

        # Update relationships to point to canonical entity
        relationships = self.service.load_table("RELATIONSHIP").to_pylist()
        updated_rels = []
        merged_rel_count = 0

        for rel in relationships:
            if rel["source_entity_id"] in merge_ids:
                rel["source_entity_id"] = keep_id
                merged_rel_count += 1
            if rel["target_entity_id"] in merge_ids:
                rel["target_entity_id"] = keep_id
                merged_rel_count += 1
            updated_rels.append(rel)

        # Deduplicate relationships (same source, target, and type)
        unique_rels = self._deduplicate_relationships(updated_rels)

        # Write back to storage
        final_entities = other_entities + [merged_entity]
        self.service.write_tables({
            "Entity": pa.Table.from_pylist(final_entities),
            "RELATIONSHIP": pa.Table.from_pylist(unique_rels)
        })

        return {
            "merged_entity_id": keep_id,
            "entities_merged": len(merge_ids),
            "relationships_updated": merged_rel_count,
            "relationships_deduplicated": len(updated_rels) - len(unique_rels),
        }

    # Helper methods

    def _generate_entity_id(self, seed: str) -> str:
        """Generate a deterministic entity ID"""
        return hashlib.md5(seed.encode()).hexdigest()[:16]

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        import re
        # Remove titles, extra spaces, and normalize case
        name = re.sub(r'\b(mr|mrs|ms|dr|prof)\.?\s+', '', name.lower())
        name = re.sub(r'[^\w\s]', '', name)
        return ' '.join(name.split())

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison"""
        import re
        # Remove all non-digits
        return re.sub(r'\D', '', phone)

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity using various techniques"""
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Token overlap (handles middle name variations)
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())

        if not tokens1 or not tokens2:
            return 0.0

        overlap = len(tokens1 & tokens2)
        total = len(tokens1 | tokens2)

        return overlap / total if total > 0 else 0.0

    def _graph_context_similarity(self, entity_id_1: str, entity_id_2: str) -> float:
        """
        Calculate similarity based on shared graph context
        (e.g., do they work at the same companies?)
        """
        # Get all connections for both entities
        query = f"""
        MATCH (e1:Entity {{entity_id: '{entity_id_1}'}})-[r1:RELATIONSHIP]-(n1:Entity)
        RETURN n1.entity_id AS connected_id, r1.relationship_type AS rel_type
        """
        result1 = self.service.run(query)
        connections1 = set()
        for i in range(result1.num_rows):
            conn_id = result1["connected_id"][i].as_py()
            rel_type = result1["rel_type"][i].as_py()
            connections1.add((conn_id, rel_type))

        query = f"""
        MATCH (e2:Entity {{entity_id: '{entity_id_2}'}})-[r2:RELATIONSHIP]-(n2:Entity)
        RETURN n2.entity_id AS connected_id, r2.relationship_type AS rel_type
        """
        result2 = self.service.run(query)
        connections2 = set()
        for i in range(result2.num_rows):
            conn_id = result2["connected_id"][i].as_py()
            rel_type = result2["rel_type"][i].as_py()
            connections2.add((conn_id, rel_type))

        # Calculate Jaccard similarity of connections
        if not connections1 and not connections2:
            return 0.0

        overlap = len(connections1 & connections2)
        total = len(connections1 | connections2)

        return overlap / total if total > 0 else 0.0

    def _get_entity_details(self, entity_id: str) -> Dict[str, Any]:
        """Get full details for an entity"""
        query = f"MATCH (e:Entity) WHERE e.entity_id = '{entity_id}' RETURN e"
        result = self.service.run(query)

        if result.num_rows == 0:
            return {}

        entity = {}
        for column in result.column_names:
            entity[column] = result[column][0].as_py()

        return entity

    def _get_entity_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for an entity"""
        query = f"""
        MATCH (e:Entity {{entity_id: '{entity_id}'}})-[r:RELATIONSHIP]-(other:Entity)
        RETURN other.name AS connected_to, r.relationship_type AS relationship, r.description AS description
        """
        result = self.service.run(query)

        relationships = []
        for i in range(result.num_rows):
            relationships.append({
                "connected_to": result["connected_to"][i].as_py(),
                "relationship": result["relationship"][i].as_py(),
                "description": result["description"][i].as_py() if "description" in result.column_names else None,
            })

        return relationships

    def _merge_entity_properties(
        self,
        keep_entity: Dict[str, Any],
        merge_entities: List[Dict[str, Any]],
        strategy: str
    ) -> Dict[str, Any]:
        """Merge properties from multiple entities"""
        merged = keep_entity.copy()

        if strategy == "prefer_keep":
            # Already using keep_entity, just return it
            return merged

        elif strategy == "prefer_complete":
            # Fill in missing values from merge_entities
            for entity in merge_entities:
                for key, value in entity.items():
                    if key not in merged or merged[key] is None:
                        merged[key] = value

        elif strategy == "merge_all":
            # Combine unique values (for fields that can have multiple values)
            # This is more complex and depends on your schema
            for entity in merge_entities:
                for key, value in entity.items():
                    if key in ["entity_id", "embedding"]:
                        continue  # Don't merge these
                    if merged.get(key) != value and value is not None:
                        # Could append to context or create combined field
                        if "context" in merged:
                            merged["context"] += f" | Alt: {value}"

        return merged

    def _deduplicate_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate relationships"""
        seen = set()
        unique = []

        for rel in relationships:
            # Create a key from source, target, and type
            key = (
                rel["source_entity_id"],
                rel["target_entity_id"],
                rel["relationship_type"]
            )

            if key not in seen:
                seen.add(key)
                unique.append(rel)

        return unique

    def _get_or_create_organization(
        self,
        company_name: str,
        organizations: Dict[str, Dict[str, Any]]
    ) -> str:
        """Get or create organization entity"""
        org_id = self._generate_entity_id(f"org_{company_name}")

        if org_id not in organizations:
            embedding = self.embedding_gen.embed_one(company_name)
            organizations[org_id] = {
                "entity_id": org_id,
                "name": company_name,
                "entity_type": "ORGANIZATION",
                "context": "",
                "embedding": embedding,
                "name_lower": company_name.lower(),
                "email": None,
                "phone": None,
                "linkedin": None,
            }

        return org_id


def demo_entity_resolution():
    """
    Demo: Person with contact info across multiple company moves
    """
    # Sample data: Same person across different jobs with varying contact info
    raw_records = [
        RawContactRecord(
            name="Alice M. Smith",
            email="alice.smith@techcorp.com",
            phone="555-0123",
            company="TechCorp",
            job_title="Software Engineer",
            linkedin="linkedin.com/in/alicesmith",
            start_date="2020-01-01",
            end_date="2022-06-30"
        ),
        RawContactRecord(
            name="Alice Smith",
            email="alice.smith@innovate.io",
            phone="555-0123",
            company="Innovate Labs",
            job_title="Senior Software Engineer",
            linkedin="linkedin.com/in/alicesmith",
            start_date="2022-07-01",
            end_date="2024-03-15"
        ),
        RawContactRecord(
            name="A. Smith",  # Abbreviated name
            email="asmith@startup.com",
            phone="555-0123",
            company="Stealth Startup",
            job_title="Engineering Lead",
            linkedin="linkedin.com/in/alicesmith",
            start_date="2024-04-01",
            end_date=None  # Current job
        ),
        RawContactRecord(
            name="Bob Johnson",
            email="bob.johnson@techcorp.com",
            phone="555-9999",
            company="TechCorp",
            job_title="Product Manager",
            start_date="2019-01-01",
        ),
    ]

    # Initialize service
    service = create_default_service()
    service.ensure_initialized()

    # Initialize resolver
    resolver = EntityResolver(service)

    print("=" * 80)
    print("Entity Resolution Demo: Contact Info Across Company Moves")
    print("=" * 80)

    # Step 1: Ingest data
    print("\n[Step 1] Ingesting contact records...")
    created = resolver.ingest_contact_records(raw_records)
    print(f"Created {len(created.get('PERSON', []))} person entities")
    print(f"Created {len(created.get('ORGANIZATION', []))} organization entities")

    # Step 2: Find duplicates
    print("\n[Step 2] Finding duplicate candidates...")
    matches = resolver.find_duplicate_candidates(entity_type="PERSON")
    print(f"Found {len(matches)} potential duplicate pairs")

    for i, match in enumerate(matches[:5], 1):  # Show top 5
        print(f"\n  Match {i}:")
        print(f"    Similarity: {match.similarity_score:.2f}")
        print(f"    Reasons: {', '.join(match.match_reasons)}")
        print(f"    Shared: {match.shared_context}")

    # Step 3: Get merge suggestions
    print("\n[Step 3] Getting merge suggestions with context...")
    suggestions = resolver.get_merge_suggestions(min_confidence=0.7)

    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n  Suggestion {i} (Confidence: {suggestion['confidence']:.2f}):")
        print(f"    Entity 1: {suggestion['entity_1']['name']} ({suggestion['entity_1']['email']})")
        if 'relationships' in suggestion['entity_1']:
            print(f"      Works at: {[r['connected_to'] for r in suggestion['entity_1']['relationships']]}")

        print(f"    Entity 2: {suggestion['entity_2']['name']} ({suggestion['entity_2']['email']})")
        if 'relationships' in suggestion['entity_2']:
            print(f"      Works at: {[r['connected_to'] for r in suggestion['entity_2']['relationships']]}")

        print(f"    Reasons: {', '.join(suggestion['match_reasons'])}")

    # Step 4: Auto-merge high-confidence duplicates
    print("\n[Step 4] Merging high-confidence duplicates...")

    if suggestions and suggestions[0]['confidence'] > 0.9:
        keep_id = suggestions[0]['entity_1']['id']
        merge_ids = [suggestions[0]['entity_2']['id']]

        # Check if there are more matches for the same entity
        for s in suggestions[1:]:
            if s['entity_1']['id'] == keep_id and s['confidence'] > 0.9:
                merge_ids.append(s['entity_2']['id'])

        result = resolver.merge_entities(
            keep_id=keep_id,
            merge_ids=merge_ids,
            merge_strategy="prefer_complete"
        )

        print(f"  Merged {result['entities_merged']} entities into {result['merged_entity_id']}")
        print(f"  Updated {result['relationships_updated']} relationships")
        print(f"  Deduplicated {result['relationships_deduplicated']} duplicate relationships")
    else:
        print("  No high-confidence matches found for auto-merge")

    # Step 5: Verify results
    print("\n[Step 5] Verifying final state...")
    query = "MATCH (p:Entity) WHERE p.entity_type = 'PERSON' RETURN p.name, p.email"
    result = service.run(query)
    print(f"  Final person count: {result.num_rows}")
    for i in range(result.num_rows):
        name = result["p.name"][i].as_py()
        email = result["p.email"][i].as_py()
        print(f"    - {name} ({email})")

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80)


if __name__ == "__main__":
    demo_entity_resolution()
