"""
Simplified Entity Resolution Demo (No Dependencies Required)

This demonstrates the entity resolution algorithm and design without requiring
the full lance-graph build. It simulates the resolution process using pure Python.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import hashlib
import re
from collections import defaultdict


@dataclass
class RawContactRecord:
    """Raw data record for a person's contact information"""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    linkedin: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class Entity:
    """Simplified entity representation"""
    entity_id: str
    name: str
    entity_type: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    context: str = ""


@dataclass
class Relationship:
    """Simplified relationship representation"""
    source_id: str
    target_id: str
    rel_type: str
    description: str = ""


@dataclass
class EntityMatch:
    """Represents a potential duplicate entity match"""
    entity_id_1: str
    entity_id_2: str
    name_1: str
    name_2: str
    similarity_score: float
    match_reasons: List[str]
    shared_context: Dict[str, Any]


class SimpleEntityResolver:
    """
    Simplified Entity Resolution demonstration
    """

    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []

    def _generate_entity_id(self, seed: str) -> str:
        """Generate a deterministic entity ID"""
        return hashlib.md5(seed.encode()).hexdigest()[:16]

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        # Remove titles, extra spaces, and normalize case
        name = re.sub(r'\b(mr|mrs|ms|dr|prof)\.?\s+', '', name.lower())
        name = re.sub(r'[^\w\s]', '', name)
        return ' '.join(name.split())

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison"""
        # Remove all non-digits
        return re.sub(r'\D', '', phone)

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity using token overlap"""
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

    def ingest_contact_records(self, records: List[RawContactRecord]) -> Dict[str, List[str]]:
        """
        Ingest raw contact records and create Person and Organization entities
        """
        print("\n📥 Ingesting contact records...")

        for idx, record in enumerate(records):
            # Create Person entity
            person_id = self._generate_entity_id(f"person_{record.name}_{idx}")

            entity = Entity(
                entity_id=person_id,
                name=record.name,
                entity_type="PERSON",
                email=record.email,
                phone=record.phone,
                linkedin=record.linkedin,
                context=f"Email: {record.email or 'N/A'}, Phone: {record.phone or 'N/A'}"
            )

            self.entities[person_id] = entity
            print(f"  ✓ Created person: {record.name} (ID: {person_id[:8]}...)")

            # Create Organization entity if company specified
            if record.company:
                org_id = self._generate_entity_id(f"org_{record.company}")

                if org_id not in self.entities:
                    org = Entity(
                        entity_id=org_id,
                        name=record.company,
                        entity_type="ORGANIZATION"
                    )
                    self.entities[org_id] = org
                    print(f"  ✓ Created organization: {record.company}")

                # Create WORKS_AT relationship
                rel = Relationship(
                    source_id=person_id,
                    target_id=org_id,
                    rel_type="WORKS_AT",
                    description=f"{record.job_title or 'Employee'} from {record.start_date or 'unknown'} to {record.end_date or 'present'}"
                )
                self.relationships.append(rel)

        # Count entities by type
        created = defaultdict(list)
        for entity in self.entities.values():
            created[entity.entity_type].append(entity.entity_id)

        return dict(created)

    def find_duplicate_candidates(self) -> List[EntityMatch]:
        """
        Find potential duplicate PERSON entities using multiple strategies
        """
        print("\n🔍 Finding duplicate candidates...")

        matches = []
        person_entities = [e for e in self.entities.values() if e.entity_type == "PERSON"]

        # Compare all pairs
        for i, entity1 in enumerate(person_entities):
            for entity2 in person_entities[i+1:]:
                match_reasons = []
                scores = []
                shared_context = {}

                # Strategy 1: Exact email match
                if entity1.email and entity2.email and entity1.email == entity2.email:
                    match_reasons.append("exact_email")
                    scores.append(1.0)
                    shared_context["email"] = entity1.email

                # Strategy 2: Exact phone match
                if entity1.phone and entity2.phone:
                    phone1 = self._normalize_phone(entity1.phone)
                    phone2 = self._normalize_phone(entity2.phone)
                    if phone1 == phone2:
                        match_reasons.append("exact_phone")
                        scores.append(1.0)
                        shared_context["phone"] = entity1.phone

                # Strategy 3: Exact LinkedIn match
                if entity1.linkedin and entity2.linkedin and entity1.linkedin == entity2.linkedin:
                    match_reasons.append("exact_linkedin")
                    scores.append(1.0)
                    shared_context["linkedin"] = entity1.linkedin

                # Strategy 4: Fuzzy name matching
                name_sim = self._name_similarity(entity1.name, entity2.name)
                if name_sim > 0.6:  # Lower threshold for name similarity
                    match_reasons.append(f"fuzzy_name_{name_sim:.2f}")
                    scores.append(name_sim)

                # Strategy 5: Graph context (shared companies)
                context_score = self._get_shared_companies(entity1.entity_id, entity2.entity_id)
                if context_score > 0:
                    match_reasons.append(f"shared_companies_{context_score}")
                    scores.append(min(context_score * 0.5, 1.0))  # Weight shared companies lower
                    shared_context["shared_companies"] = context_score

                # If any strategy found a match, create an EntityMatch
                if scores:
                    # Weighted average (exact matches weighted higher)
                    weights = [2.0 if "exact_" in reason else 1.0 for reason in match_reasons]
                    weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

                    if weighted_score >= self.similarity_threshold:
                        matches.append(EntityMatch(
                            entity_id_1=entity1.entity_id,
                            entity_id_2=entity2.entity_id,
                            name_1=entity1.name,
                            name_2=entity2.name,
                            similarity_score=weighted_score,
                            match_reasons=match_reasons,
                            shared_context=shared_context
                        ))

        # Sort by similarity score
        matches.sort(key=lambda x: x.similarity_score, reverse=True)

        print(f"  ✓ Found {len(matches)} potential duplicate pairs")
        return matches

    def _get_shared_companies(self, entity_id_1: str, entity_id_2: str) -> int:
        """Count shared companies between two people"""
        # Get companies for entity 1
        companies_1 = set()
        for rel in self.relationships:
            if rel.source_id == entity_id_1 and rel.rel_type == "WORKS_AT":
                companies_1.add(rel.target_id)

        # Get companies for entity 2
        companies_2 = set()
        for rel in self.relationships:
            if rel.source_id == entity_id_2 and rel.rel_type == "WORKS_AT":
                companies_2.add(rel.target_id)

        return len(companies_1 & companies_2)

    def print_merge_suggestions(self, matches: List[EntityMatch]):
        """
        Print human-readable merge suggestions
        """
        print("\n💡 Merge Suggestions:")
        print("=" * 80)

        if not matches:
            print("  No duplicates found!")
            return

        for i, match in enumerate(matches, 1):
            entity1 = self.entities[match.entity_id_1]
            entity2 = self.entities[match.entity_id_2]

            print(f"\nSuggestion #{i}  (Confidence: {match.similarity_score:.1%})")
            print("-" * 80)

            print(f"  Entity 1: {entity1.name}")
            print(f"    ID: {entity1.entity_id[:8]}...")
            print(f"    Email: {entity1.email or 'N/A'}")
            print(f"    Phone: {entity1.phone or 'N/A'}")
            print(f"    LinkedIn: {entity1.linkedin or 'N/A'}")

            # Show relationships
            companies_1 = [
                self.entities[rel.target_id].name
                for rel in self.relationships
                if rel.source_id == entity1.entity_id and rel.rel_type == "WORKS_AT"
            ]
            if companies_1:
                print(f"    Companies: {', '.join(companies_1)}")

            print(f"\n  Entity 2: {entity2.name}")
            print(f"    ID: {entity2.entity_id[:8]}...")
            print(f"    Email: {entity2.email or 'N/A'}")
            print(f"    Phone: {entity2.phone or 'N/A'}")
            print(f"    LinkedIn: {entity2.linkedin or 'N/A'}")

            # Show relationships
            companies_2 = [
                self.entities[rel.target_id].name
                for rel in self.relationships
                if rel.source_id == entity2.entity_id and rel.rel_type == "WORKS_AT"
            ]
            if companies_2:
                print(f"    Companies: {', '.join(companies_2)}")

            print(f"\n  Match Reasons: {', '.join(match.match_reasons)}")
            print(f"  Shared Context: {match.shared_context}")

    def merge_entities(self, keep_id: str, merge_ids: List[str]) -> Dict[str, Any]:
        """
        Merge duplicate entities into a canonical entity
        """
        print(f"\n🔄 Merging entities into {keep_id[:8]}...")

        # Update relationships
        merged_rel_count = 0
        for rel in self.relationships:
            if rel.source_id in merge_ids:
                rel.source_id = keep_id
                merged_rel_count += 1
            if rel.target_id in merge_ids:
                rel.target_id = keep_id
                merged_rel_count += 1

        # Deduplicate relationships
        unique_rels = []
        seen = set()
        for rel in self.relationships:
            key = (rel.source_id, rel.target_id, rel.rel_type)
            if key not in seen:
                seen.add(key)
                unique_rels.append(rel)

        dedup_count = len(self.relationships) - len(unique_rels)
        self.relationships = unique_rels

        # Remove duplicate entities
        for merge_id in merge_ids:
            if merge_id in self.entities:
                del self.entities[merge_id]

        return {
            "merged_entity_id": keep_id,
            "entities_merged": len(merge_ids),
            "relationships_updated": merged_rel_count,
            "relationships_deduplicated": dedup_count,
        }

    def print_final_state(self):
        """Print the final state of entities"""
        print("\n📊 Final Entity State:")
        print("=" * 80)

        person_entities = [e for e in self.entities.values() if e.entity_type == "PERSON"]
        print(f"\nTotal Persons: {len(person_entities)}\n")

        for entity in person_entities:
            print(f"  • {entity.name}")
            print(f"    Email: {entity.email or 'N/A'}")
            print(f"    Phone: {entity.phone or 'N/A'}")

            # Show companies
            companies = [
                self.entities[rel.target_id].name
                for rel in self.relationships
                if rel.source_id == entity.entity_id and rel.rel_type == "WORKS_AT"
            ]
            if companies:
                print(f"    Companies: {', '.join(companies)}")
            print()


def demo():
    """
    Demo: Person with contact info across multiple company moves
    """
    print("=" * 80)
    print("Entity Resolution Demo: Contact Info Across Company Moves")
    print("=" * 80)

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
            name="Alice Smith",  # Slightly different name
            email="alice.smith@innovate.io",
            phone="555-0123",  # Same phone
            company="Innovate Labs",
            job_title="Senior Software Engineer",
            linkedin="linkedin.com/in/alicesmith",  # Same LinkedIn
            start_date="2022-07-01",
            end_date="2024-03-15"
        ),
        RawContactRecord(
            name="A. Smith",  # Abbreviated name
            email="asmith@startup.com",
            phone="555-0123",  # Same phone again
            company="Stealth Startup",
            job_title="Engineering Lead",
            linkedin="linkedin.com/in/alicesmith",  # Same LinkedIn
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
        RawContactRecord(
            name="Alice M Smith",  # No period, testing fuzzy match
            email="alice@personal.com",
            phone="555-0123",  # Same phone
            company="TechCorp",
            job_title="Software Engineer",
            start_date="2020-01-01",
            end_date="2022-06-30"
        ),
    ]

    # Initialize resolver
    resolver = SimpleEntityResolver(similarity_threshold=0.7)

    # Step 1: Ingest data
    print("\n[Step 1] Ingesting Contact Records")
    print("-" * 80)
    created = resolver.ingest_contact_records(raw_records)
    print(f"\n✓ Created {len(created.get('PERSON', []))} person entities")
    print(f"✓ Created {len(created.get('ORGANIZATION', []))} organization entities")

    # Step 2: Find duplicates
    print("\n[Step 2] Detecting Duplicates")
    print("-" * 80)
    matches = resolver.find_duplicate_candidates()

    # Step 3: Show merge suggestions
    print("\n[Step 3] Merge Suggestions")
    print("-" * 80)
    resolver.print_merge_suggestions(matches)

    # Step 4: Auto-merge high-confidence duplicates
    print("\n\n[Step 4] Executing Merges")
    print("-" * 80)

    # Group matches by primary entity
    merge_groups = defaultdict(list)
    processed = set()

    for match in matches:
        if match.similarity_score > 0.9:  # High confidence threshold
            if match.entity_id_1 not in processed and match.entity_id_2 not in processed:
                merge_groups[match.entity_id_1].append(match.entity_id_2)
                processed.add(match.entity_id_2)

    if merge_groups:
        for keep_id, merge_ids in merge_groups.items():
            result = resolver.merge_entities(keep_id, merge_ids)
            print(f"\n  ✓ Merged {result['entities_merged']} entities into {keep_id[:8]}...")
            print(f"    • Updated {result['relationships_updated']} relationships")
            print(f"    • Deduplicated {result['relationships_deduplicated']} duplicate relationships")
    else:
        print("  ℹ No high-confidence matches found for auto-merge")

    # Step 5: Show final state
    print("\n[Step 5] Final Results")
    print("-" * 80)
    resolver.print_final_state()

    print("\n" + "=" * 80)
    print("Demo Complete! 🎉")
    print("=" * 80)

    print("\n📖 Summary:")
    print(f"  • Started with {len(raw_records)} contact records")
    print(f"  • Detected {len(matches)} potential duplicates")
    print(f"  • Final person count: {len([e for e in resolver.entities.values() if e.entity_type == 'PERSON'])}")
    print("\n💡 Key Insights:")
    print("  • Multiple resolution strategies (exact identifiers, fuzzy names, graph context)")
    print("  • Confidence scoring helps prioritize review")
    print("  • Relationship preservation maintains data integrity")
    print("  • This approach scales to Person, Organization, and Event entities")


if __name__ == "__main__":
    demo()
