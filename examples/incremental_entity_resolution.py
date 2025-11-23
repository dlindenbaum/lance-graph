"""
Incremental Entity Resolution: Check Before Creating New Nodes

This demonstrates how to handle incoming raw data by checking for duplicates
BEFORE creating new nodes, avoiding the need to clean up later.
"""

from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
import hashlib
import re


@dataclass
class RawContactRecord:
    """Incoming raw data"""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    company: Optional[str] = None


@dataclass
class ResolutionDecision:
    """Decision about what to do with incoming data"""
    action: str  # "create_new", "link_existing", "needs_review"
    confidence: float
    matched_entity_id: Optional[str] = None
    reasons: List[str] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []


class IncrementalEntityResolver:
    """
    Entity resolver that checks for matches BEFORE creating nodes
    """

    def __init__(self, service, similarity_threshold=0.85, auto_link_threshold=0.95):
        self.service = service
        self.similarity_threshold = similarity_threshold
        self.auto_link_threshold = auto_link_threshold

    def should_create_new_entity(
        self,
        candidate: RawContactRecord
    ) -> ResolutionDecision:
        """
        Check if we should create a new entity or link to existing one

        Returns:
            ResolutionDecision with action and reasoning
        """

        # Step 1: Fast exact match checks (blockers)
        if candidate.email:
            existing = self._find_by_exact_match("email", candidate.email)
            if existing:
                return ResolutionDecision(
                    action="link_existing",
                    confidence=1.0,
                    matched_entity_id=existing["entity_id"],
                    reasons=["exact_email_match"]
                )

        if candidate.linkedin:
            existing = self._find_by_exact_match("linkedin", candidate.linkedin)
            if existing:
                return ResolutionDecision(
                    action="link_existing",
                    confidence=1.0,
                    matched_entity_id=existing["entity_id"],
                    reasons=["exact_linkedin_match"]
                )

        if candidate.phone:
            phone_normalized = self._normalize_phone(candidate.phone)
            existing = self._find_by_normalized_phone(phone_normalized)
            if existing:
                return ResolutionDecision(
                    action="link_existing",
                    confidence=1.0,
                    matched_entity_id=existing["entity_id"],
                    reasons=["exact_phone_match"]
                )

        # Step 2: Fuzzy matching by name
        name_candidates = self._find_by_fuzzy_name(candidate.name)

        if not name_candidates:
            # No matches found - safe to create new
            return ResolutionDecision(
                action="create_new",
                confidence=1.0,
                reasons=["no_matches_found"]
            )

        # Step 3: Score name candidates with additional signals
        best_match = None
        best_score = 0.0

        for existing in name_candidates:
            score, reasons = self._calculate_match_score(candidate, existing)

            if score > best_score:
                best_score = score
                best_match = existing
                best_reasons = reasons

        # Step 4: Decide based on threshold
        if best_score >= self.auto_link_threshold:
            return ResolutionDecision(
                action="link_existing",
                confidence=best_score,
                matched_entity_id=best_match["entity_id"],
                reasons=best_reasons
            )
        elif best_score >= self.similarity_threshold:
            return ResolutionDecision(
                action="needs_review",
                confidence=best_score,
                matched_entity_id=best_match["entity_id"],
                reasons=best_reasons
            )
        else:
            return ResolutionDecision(
                action="create_new",
                confidence=1.0 - best_score,
                reasons=["no_high_confidence_matches"]
            )

    def process_incoming_record(
        self,
        record: RawContactRecord,
        auto_link: bool = True
    ) -> Tuple[str, str]:
        """
        Process incoming record and return (entity_id, action_taken)

        Args:
            record: The incoming raw data
            auto_link: If True, automatically link high-confidence matches

        Returns:
            (entity_id, action) where action is "created", "linked", or "flagged_for_review"
        """

        decision = self.should_create_new_entity(record)

        print(f"\n📋 Processing: {record.name}")
        print(f"   Decision: {decision.action} (confidence: {decision.confidence:.1%})")
        print(f"   Reasons: {', '.join(decision.reasons)}")

        if decision.action == "create_new":
            entity_id = self._create_entity(record)
            return entity_id, "created"

        elif decision.action == "link_existing":
            if auto_link:
                self._add_context_to_existing(decision.matched_entity_id, record)
                return decision.matched_entity_id, "linked"
            else:
                entity_id = self._create_entity(record)
                self._flag_for_review(entity_id, decision.matched_entity_id, decision)
                return entity_id, "flagged_for_review"

        else:  # needs_review
            entity_id = self._create_entity(record)
            self._flag_for_review(entity_id, decision.matched_entity_id, decision)
            return entity_id, "flagged_for_review"

    def batch_process_with_dedup(
        self,
        records: List[RawContactRecord],
        auto_link: bool = True
    ) -> Dict[str, Any]:
        """
        Process a batch of records with incremental deduplication

        Returns statistics about the processing
        """

        stats = {
            "total_records": len(records),
            "created": 0,
            "linked": 0,
            "flagged": 0,
            "entity_ids": []
        }

        print(f"\n{'='*80}")
        print(f"Processing {len(records)} incoming records")
        print(f"{'='*80}")

        for record in records:
            entity_id, action = self.process_incoming_record(record, auto_link)
            stats["entity_ids"].append(entity_id)

            if action == "created":
                stats["created"] += 1
            elif action == "linked":
                stats["linked"] += 1
            else:
                stats["flagged"] += 1

        print(f"\n{'='*80}")
        print(f"Processing Complete")
        print(f"{'='*80}")
        print(f"  Created: {stats['created']}")
        print(f"  Linked to existing: {stats['linked']}")
        print(f"  Flagged for review: {stats['flagged']}")
        print(f"  Unique entities: {len(set(stats['entity_ids']))}")

        return stats

    # Helper methods

    def _find_by_exact_match(self, field: str, value: str) -> Optional[Dict]:
        """Find entity by exact field match"""
        query = f"MATCH (e:Entity) WHERE e.{field} = '{value}' RETURN e LIMIT 1"
        result = self.service.run(query)

        if result.num_rows > 0:
            entity = {}
            for col in result.column_names:
                entity[col.replace("e.", "")] = result[col][0].as_py()
            return entity
        return None

    def _find_by_normalized_phone(self, phone_normalized: str) -> Optional[Dict]:
        """Find by normalized phone number"""
        # In production, you'd normalize all phones and store separately
        # For demo, we'll check all entities
        query = "MATCH (e:Entity) WHERE e.phone IS NOT NULL RETURN e"
        result = self.service.run(query)

        for i in range(result.num_rows):
            entity = {}
            for col in result.column_names:
                entity[col.replace("e.", "")] = result[col][i].as_py()

            if entity.get("phone"):
                if self._normalize_phone(entity["phone"]) == phone_normalized:
                    return entity

        return None

    def _find_by_fuzzy_name(self, name: str, limit: int = 5) -> List[Dict]:
        """Find entities with similar names"""
        normalized = self._normalize_name(name)

        # Get all person entities (in production, use better indexing)
        query = "MATCH (e:Entity) WHERE e.entity_type = 'PERSON' RETURN e"
        result = self.service.run(query)

        candidates = []
        for i in range(result.num_rows):
            entity = {}
            for col in result.column_names:
                entity[col.replace("e.", "")] = result[col][i].as_py()

            # Calculate name similarity
            existing_normalized = self._normalize_name(entity.get("name", ""))
            similarity = self._name_similarity(normalized, existing_normalized)

            if similarity > 0.6:  # Threshold for candidates
                entity["_name_similarity"] = similarity
                candidates.append(entity)

        # Sort by similarity
        candidates.sort(key=lambda x: x["_name_similarity"], reverse=True)
        return candidates[:limit]

    def _calculate_match_score(
        self,
        candidate: RawContactRecord,
        existing: Dict
    ) -> Tuple[float, List[str]]:
        """Calculate match score between candidate and existing entity"""

        scores = []
        weights = []
        reasons = []

        # Name similarity (from fuzzy search)
        if "_name_similarity" in existing:
            scores.append(existing["_name_similarity"])
            weights.append(1.0)
            reasons.append(f"name_similarity_{existing['_name_similarity']:.2f}")

        # Email match
        if candidate.email and existing.get("email"):
            if candidate.email == existing["email"]:
                scores.append(1.0)
                weights.append(2.0)  # Exact matches weighted higher
                reasons.append("exact_email")

        # Phone match
        if candidate.phone and existing.get("phone"):
            if self._normalize_phone(candidate.phone) == self._normalize_phone(existing["phone"]):
                scores.append(1.0)
                weights.append(2.0)
                reasons.append("exact_phone")

        # LinkedIn match
        if candidate.linkedin and existing.get("linkedin"):
            if candidate.linkedin == existing["linkedin"]:
                scores.append(1.0)
                weights.append(2.0)
                reasons.append("exact_linkedin")

        if not scores:
            return 0.0, []

        # Weighted average
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        return weighted_score, reasons

    def _create_entity(self, record: RawContactRecord) -> str:
        """Create a new entity from record"""
        entity_id = hashlib.md5(f"{record.name}{record.email}".encode()).hexdigest()[:16]

        # In production, use embedding generator
        entity = {
            "entity_id": entity_id,
            "name": record.name,
            "entity_type": "PERSON",
            "email": record.email,
            "phone": record.phone,
            "linkedin": record.linkedin,
            "context": f"Created from incoming data"
        }

        # Simulate adding to graph
        print(f"   ✓ Created new entity: {entity_id[:8]}...")
        return entity_id

    def _add_context_to_existing(self, entity_id: str, record: RawContactRecord):
        """Add additional context to existing entity"""
        print(f"   ✓ Linked to existing entity: {entity_id[:8]}...")

        # In production:
        # - Update entity with any new non-null fields
        # - Add relationship if company specified
        # - Log the linkage

    def _flag_for_review(self, new_id: str, potential_match_id: str, decision: ResolutionDecision):
        """Flag potential duplicate for human review"""
        print(f"   ⚠ Flagged for review: {new_id[:8]} vs {potential_match_id[:8]}")

        # In production:
        # - Create a "PotentialDuplicate" relationship
        # - Add to review queue
        # - Notify human reviewer

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        name = re.sub(r'\b(mr|mrs|ms|dr|prof)\.?\s+', '', name.lower())
        name = re.sub(r'[^\w\s]', '', name)
        return ' '.join(name.split())

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number"""
        return re.sub(r'\D', '', phone)

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity"""
        if name1 == name2:
            return 1.0

        tokens1 = set(name1.split())
        tokens2 = set(name2.split())

        if not tokens1 or not tokens2:
            return 0.0

        overlap = len(tokens1 & tokens2)
        total = len(tokens1 | tokens2)

        return overlap / total if total > 0 else 0.0


# Mock service for demo
class MockService:
    def __init__(self):
        self.entities = []

    def run(self, query):
        # Simple mock that returns empty results
        import pyarrow as pa
        return pa.Table.from_pydict({"e.entity_id": [], "e.name": [], "e.email": []})


def demo():
    """Demonstrate incremental entity resolution"""

    print("="*80)
    print("Incremental Entity Resolution Demo")
    print("="*80)
    print("\nScenario: New contact records arrive in batches")
    print("Goal: Determine if we should create new nodes or link to existing ones\n")

    # Simulated existing data (already in graph)
    print("📊 Existing entities in graph:")
    print("  • Alice Smith (alice@techcorp.com, 555-0123)")
    print("  • Bob Johnson (bob@techcorp.com, 555-9999)")

    # New incoming records
    incoming_records = [
        RawContactRecord(
            name="Alice M. Smith",  # Similar to existing Alice Smith
            email="alice@techcorp.com",  # EXACT match
            phone="555-0123",
            linkedin="linkedin.com/in/alicesmith"
        ),
        RawContactRecord(
            name="Alice Smith",  # Exact name match
            email="alice.smith@newco.com",  # Different email
            phone="555-0123",  # Same phone
            linkedin="linkedin.com/in/alicesmith"  # Same LinkedIn
        ),
        RawContactRecord(
            name="Alicia Smith",  # Typo?
            email="alicia@startup.com",
            phone="555-0124",  # Different phone
            linkedin=None
        ),
        RawContactRecord(
            name="Carol White",  # Completely new person
            email="carol@newcompany.com",
            phone="555-7777",
            linkedin="linkedin.com/in/carolwhite"
        ),
    ]

    # Mock the service (in production, use real service)
    service = MockService()
    resolver = IncrementalEntityResolver(
        service,
        similarity_threshold=0.85,
        auto_link_threshold=0.95
    )

    # For demo purposes, manually simulate the decisions
    print("\n" + "="*80)
    print("Processing Incoming Records")
    print("="*80)

    print("\n📋 Record 1: Alice M. Smith")
    print("   Email: alice@techcorp.com (EXACT MATCH with existing)")
    print("   ✓ Decision: LINK TO EXISTING")
    print("   Confidence: 100%")
    print("   Reason: Exact email match is a blocker - definitely same person")

    print("\n📋 Record 2: Alice Smith")
    print("   Phone: 555-0123 (matches existing)")
    print("   LinkedIn: linkedin.com/in/alicesmith (matches existing)")
    print("   Email: alice.smith@newco.com (NEW)")
    print("   ✓ Decision: LINK TO EXISTING")
    print("   Confidence: 100%")
    print("   Reason: Same phone + LinkedIn = same person, new job email")

    print("\n📋 Record 3: Alicia Smith")
    print("   Name: Similar to 'Alice Smith' (possible typo)")
    print("   Phone: 555-0124 (close to 555-0123 but different)")
    print("   Email: alicia@startup.com (no match)")
    print("   ⚠ Decision: FLAG FOR REVIEW")
    print("   Confidence: 75%")
    print("   Reason: Name similarity but no exact identifiers - could be typo or different person")

    print("\n📋 Record 4: Carol White")
    print("   Name: No similarity to existing entities")
    print("   Email: carol@newcompany.com (no match)")
    print("   Phone: 555-7777 (no match)")
    print("   ✓ Decision: CREATE NEW ENTITY")
    print("   Confidence: 100%")
    print("   Reason: No matches found anywhere")

    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print("\n✅ Recommended Workflow:\n")
    print("1. EXACT MATCH checks (email, phone, LinkedIn)")
    print("   → If found: Link immediately (100% confidence)")
    print("\n2. FUZZY NAME search")
    print("   → Find candidates with similar names")
    print("\n3. SCORE candidates with multiple signals")
    print("   → Combine name similarity + other attributes")
    print("\n4. DECIDE based on thresholds:")
    print("   • >95%: Auto-link")
    print("   • 85-95%: Flag for human review")
    print("   • <85%: Create new entity")
    print("\n5. LEARN from human feedback")
    print("   → Adjust thresholds over time")

    print("\n" + "="*80)
    print("Key Benefits of Check-Before-Create")
    print("="*80)
    print("\n✓ Prevents duplicate creation upfront")
    print("✓ Maintains cleaner graph structure")
    print("✓ Reduces need for batch cleanup jobs")
    print("✓ Provides real-time duplicate detection")
    print("✓ Enables human-in-the-loop for edge cases")

    print("\n" + "="*80)


if __name__ == "__main__":
    demo()
