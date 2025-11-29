"""Generic DuckDB tools for searching and analyzing any type of data.

These tools are domain-agnostic and work with any database schema.
Entity discovery and proposal generation are guided by the ontology.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import duckdb
except ImportError:
    duckdb = None

from .ontology import GraphOntology

logger = logging.getLogger(__name__)


class DuckDBQueryTool:
    """Generic tool for querying DuckDB databases with SQL."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        read_only: bool = True,
    ):
        """Initialize DuckDB connection.

        Args:
            db_path: Path to DuckDB database file. If None, uses in-memory database.
            read_only: If True, opens database in read-only mode.
        """
        if duckdb is None:
            raise ImportError(
                "duckdb package is required. Install with: pip install duckdb"
            )

        self.db_path = Path(db_path) if db_path else None
        self.read_only = read_only
        self.connection = self._create_connection()

    def _create_connection(self) -> "duckdb.DuckDBPyConnection":
        """Create DuckDB connection."""
        if self.db_path:
            return duckdb.connect(str(self.db_path), read_only=self.read_only)
        else:
            return duckdb.connect(":memory:")

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts.

        Args:
            query: SQL query to execute
            params: Optional query parameters for prepared statements

        Returns:
            List of dictionaries representing rows
        """
        try:
            if params:
                result = self.connection.execute(query, params).fetchall()
            else:
                result = self.connection.execute(query).fetchall()

            # Get column names
            columns = [desc[0] for desc in self.connection.description]

            # Convert to list of dicts
            return [dict(zip(columns, row)) for row in result]

        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return [{"error": str(e), "query": query}]

    def get_tables(self) -> List[str]:
        """Get list of all tables in the database."""
        try:
            result = self.connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Error getting tables: {e}")
            return []

    def get_schema(self, table_name: str) -> List[Dict[str, str]]:
        """Get schema for a specific table.

        Args:
            table_name: Name of the table

        Returns:
            List of column definitions with name, type, nullable
        """
        try:
            result = self.connection.execute(
                f"PRAGMA table_info('{table_name}')"
            ).fetchall()

            return [
                {
                    "column_name": row[1],
                    "data_type": row[2],
                    "nullable": "YES" if row[3] == 0 else "NO",
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Error getting schema for {table_name}: {e}")
            return [{"error": str(e)}]

    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample rows from a table for schema inference.

        Args:
            table_name: Name of the table
            limit: Number of sample rows to return

        Returns:
            Sample rows
        """
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute_query(query)

    def search_across_tables(
        self, search_term: str, tables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for a term across multiple tables.

        Args:
            search_term: Term to search for
            tables: List of tables to search. If None, searches all tables.

        Returns:
            Results from all tables containing the search term
        """
        if tables is None:
            tables = self.get_tables()

        results = []
        for table in tables:
            schema = self.get_schema(table)
            if not schema or "error" in schema[0]:
                continue

            # Build OR condition for all text/varchar columns
            text_columns = [
                col["column_name"]
                for col in schema
                if "VARCHAR" in col["data_type"].upper()
                or "TEXT" in col["data_type"].upper()
                or "CHAR" in col["data_type"].upper()
            ]

            if not text_columns:
                continue

            conditions = " OR ".join(
                [f"CAST({col} AS VARCHAR) LIKE '%{search_term}%'" for col in text_columns]
            )

            query = f"SELECT * FROM {table} WHERE {conditions} LIMIT 100"

            table_results = self.execute_query(query)
            for row in table_results:
                row["_source_table"] = table
                results.append(row)

        return results

    def aggregate_analysis(
        self, table: str, group_by: str, agg_column: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform aggregation analysis on a table.

        Args:
            table: Table name
            group_by: Column to group by
            agg_column: Column to aggregate. If None, just counts.

        Returns:
            Aggregated results
        """
        if agg_column:
            query = f"""
                SELECT {group_by},
                       COUNT(*) as count,
                       AVG({agg_column}) as avg_value,
                       MIN({agg_column}) as min_value,
                       MAX({agg_column}) as max_value
                FROM {table}
                GROUP BY {group_by}
                ORDER BY count DESC
                LIMIT 100
            """
        else:
            query = f"""
                SELECT {group_by}, COUNT(*) as count
                FROM {table}
                GROUP BY {group_by}
                ORDER BY count DESC
                LIMIT 100
            """

        return self.execute_query(query)

    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DataAnalysisTool:
    """Generic data analysis tools for pattern detection and insights."""

    def __init__(self, duckdb_tool: DuckDBQueryTool):
        self.db = duckdb_tool

    def find_frequent_patterns(
        self,
        table: str,
        column: str,
        min_frequency: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find frequently occurring values in a column.

        Args:
            table: Table name
            column: Column to analyze
            min_frequency: Minimum occurrence count

        Returns:
            List of frequent values with counts
        """
        query = f"""
            SELECT {column} as value,
                   COUNT(*) as frequency
            FROM {table}
            WHERE {column} IS NOT NULL
            GROUP BY {column}
            HAVING COUNT(*) >= {min_frequency}
            ORDER BY frequency DESC
            LIMIT 100
        """
        return self.db.execute_query(query)

    def find_correlations(
        self,
        table: str,
        column1: str,
        column2: str,
    ) -> List[Dict[str, Any]]:
        """Find correlations between two columns.

        Args:
            table: Table name
            column1: First column
            column2: Second column

        Returns:
            Co-occurrence patterns
        """
        query = f"""
            SELECT {column1},
                   {column2},
                   COUNT(*) as co_occurrence_count
            FROM {table}
            WHERE {column1} IS NOT NULL AND {column2} IS NOT NULL
            GROUP BY {column1}, {column2}
            HAVING COUNT(*) > 1
            ORDER BY co_occurrence_count DESC
            LIMIT 100
        """
        return self.db.execute_query(query)

    def detect_anomalies(
        self,
        table: str,
        numeric_column: str,
        std_threshold: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """Detect statistical anomalies in numeric data.

        Args:
            table: Table name
            numeric_column: Column to analyze
            std_threshold: Number of standard deviations for anomaly detection

        Returns:
            Rows with anomalous values
        """
        query = f"""
            WITH stats AS (
                SELECT AVG({numeric_column}) as mean,
                       STDDEV({numeric_column}) as std
                FROM {table}
            )
            SELECT *,
                   ABS({numeric_column} - stats.mean) / stats.std as std_from_mean
            FROM {table}, stats
            WHERE ABS({numeric_column} - stats.mean) / stats.std > {std_threshold}
            ORDER BY std_from_mean DESC
            LIMIT 100
        """
        return self.db.execute_query(query)

    def temporal_analysis(
        self,
        table: str,
        timestamp_column: str,
        group_by_interval: str = "day",
    ) -> List[Dict[str, Any]]:
        """Analyze temporal patterns in data.

        Args:
            table: Table name
            timestamp_column: Timestamp column
            group_by_interval: Interval to group by (day, hour, month)

        Returns:
            Temporal aggregation results
        """
        if group_by_interval == "hour":
            time_expr = f"DATE_TRUNC('hour', {timestamp_column})"
        elif group_by_interval == "day":
            time_expr = f"DATE_TRUNC('day', {timestamp_column})"
        elif group_by_interval == "month":
            time_expr = f"DATE_TRUNC('month', {timestamp_column})"
        else:
            time_expr = f"DATE_TRUNC('day', {timestamp_column})"

        query = f"""
            SELECT {time_expr} as time_period,
                   COUNT(*) as event_count
            FROM {table}
            WHERE {timestamp_column} IS NOT NULL
            GROUP BY time_period
            ORDER BY time_period
            LIMIT 1000
        """
        return self.db.execute_query(query)

    def find_duplicates(
        self,
        table: str,
        columns: List[str],
    ) -> List[Dict[str, Any]]:
        """Find duplicate records based on specified columns.

        Args:
            table: Table name
            columns: Columns to check for duplicates

        Returns:
            Duplicate records with counts
        """
        cols_str = ", ".join(columns)
        query = f"""
            SELECT {cols_str},
                   COUNT(*) as duplicate_count
            FROM {table}
            GROUP BY {cols_str}
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
            LIMIT 100
        """
        return self.db.execute_query(query)


class NodeProposalGenerator:
    """Generate ontology-compliant graph node proposals from data analysis."""

    def __init__(
        self,
        analysis_tool: DataAnalysisTool,
        ontology: Optional[GraphOntology] = None,
        graph_tool: Optional[Any] = None,
    ):
        self.analysis = analysis_tool
        self.db = analysis_tool.db
        self.ontology = ontology
        self.graph_tool = graph_tool

    def propose_nodes_from_column(
        self,
        table: str,
        entity_column: str,
        entity_type: str,
        property_columns: Optional[List[str]] = None,
        min_confidence: int = 50,
    ) -> List[Dict[str, Any]]:
        """Generate node proposals from a column containing entity identifiers.

        Args:
            table: Source table
            entity_column: Column containing entity identifiers
            entity_type: Type of entity (must be in ontology if ontology is set)
            property_columns: Additional columns to include as properties
            min_confidence: Minimum confidence score (0-100)

        Returns:
            List of proposed node additions
        """
        # Validate entity type against ontology
        if self.ontology:
            et = self.ontology.get_entity_type(entity_type)
            if not et:
                logger.warning(
                    f"Entity type '{entity_type}' not found in ontology. "
                    f"Valid types: {self.ontology.get_valid_entity_types()}"
                )
                return []

        # Build query to get unique entities with their properties
        select_cols = [entity_column]
        if property_columns:
            select_cols.extend(property_columns)

        cols_str = ", ".join(select_cols)
        query = f"""
            SELECT {cols_str},
                   COUNT(*) as occurrence_count
            FROM {table}
            WHERE {entity_column} IS NOT NULL
            GROUP BY {cols_str}
            ORDER BY occurrence_count DESC
            LIMIT 100
        """

        results = self.db.execute_query(query)

        proposals = []
        for row in results:
            # Calculate confidence based on occurrence count
            occurrence_count = row.get("occurrence_count", 1)
            confidence = min(100, min_confidence + (occurrence_count * 5))

            # Build properties dict
            properties = {}
            if property_columns:
                for col in property_columns:
                    if col in row and row[col] is not None:
                        properties[col] = row[col]

            properties["occurrence_count"] = occurrence_count
            properties["source_table"] = table
            properties["source_column"] = entity_column

            # Validate against ontology if present
            if self.ontology:
                is_valid, errors = self.ontology.validate_entity(entity_type, properties)
                if not is_valid:
                    logger.warning(f"Validation errors for {entity_type}: {errors}")
                    # Continue anyway but log the issue
                    properties["validation_warnings"] = errors

            proposals.append(
                {
                    "type": "add_node",
                    "entity": entity_type,
                    "label": str(row[entity_column]),
                    "properties": properties,
                    "confidence": confidence,
                    "evidence": f"Found {occurrence_count} occurrences in {table}.{entity_column}",
                }
            )

        return proposals

    def check_for_merges(
        self,
        entity_type: str,
        proposed_properties: Dict[str, Any],
        proposed_label: str,
    ) -> Optional[Dict[str, Any]]:
        """Check if a proposed node matches an existing node and should be merged.

        Args:
            entity_type: Type of entity
            proposed_properties: Properties of the proposed node
            proposed_label: Label of the proposed node

        Returns:
            Merge proposal dict if a match is found, None otherwise
        """
        if not self.ontology or not self.graph_tool:
            return None

        try:
            # Query existing nodes of this type
            existing_nodes = self.graph_tool.search_nodes(entity_type)

            if not existing_nodes:
                return None

            # Check each existing node for matches
            best_match = None
            best_confidence = 0.0
            best_matched_rules = []

            for existing_node in existing_nodes:
                existing_props = existing_node.get("properties", {})
                existing_label = existing_node.get("label", "")

                # Skip if it's the exact same label (likely already exists)
                if existing_label == proposed_label:
                    continue

                # Use ontology matching rules
                is_match, confidence, matched_rules = self.ontology.match_entities(
                    entity_type, existing_props, proposed_properties
                )

                if is_match and confidence > best_confidence:
                    best_match = existing_node
                    best_confidence = confidence
                    best_matched_rules = matched_rules

            if best_match:
                # Generate merged properties
                merged_props = self._merge_properties(
                    best_match.get("properties", {}),
                    proposed_properties,
                    entity_type,
                )

                return {
                    "type": "merge_nodes",
                    "entity": entity_type,
                    "primary_label": best_match.get("label", ""),
                    "secondary_label": proposed_label,
                    "primary_properties": best_match.get("properties", {}),
                    "secondary_properties": proposed_properties,
                    "merged_properties": merged_props,
                    "match_confidence": best_confidence,
                    "matched_rules": best_matched_rules,
                    "evidence": f"Matched on: {', '.join(best_matched_rules)} with {best_confidence:.2%} confidence",
                    "requires_review": self._requires_review(entity_type, best_confidence),
                }

            return None

        except Exception as e:
            logger.error(f"Error checking for merges: {e}")
            return None

    def _merge_properties(
        self,
        primary: Dict[str, Any],
        secondary: Dict[str, Any],
        entity_type: str,
    ) -> Dict[str, Any]:
        """Merge properties from two nodes based on merge strategy.

        Args:
            primary: Properties from primary node
            secondary: Properties from secondary node
            entity_type: Type of entity

        Returns:
            Merged properties dict
        """
        merged = dict(primary)  # Start with primary

        if not self.ontology:
            # No ontology, simple merge
            for key, value in secondary.items():
                if key not in merged or merged[key] is None:
                    merged[key] = value
            return merged

        # Get merge strategy from ontology
        et = self.ontology.get_entity_type(entity_type)
        merge_strategy = et.merge_strategy if et else None

        if not merge_strategy or merge_strategy.combine_properties:
            # Combine properties
            for key, value in secondary.items():
                if key not in merged:
                    merged[key] = value
                elif merged[key] is None and value is not None:
                    merged[key] = value
                elif merged[key] != value and value is not None:
                    # Different values - create combined field
                    if not isinstance(merged.get(key), list):
                        merged[key] = [merged[key]]
                    if value not in merged[key]:
                        merged[key].append(value)

        return merged

    def _requires_review(self, entity_type: str, confidence: float) -> bool:
        """Determine if a merge requires manual review.

        Args:
            entity_type: Type of entity
            confidence: Match confidence

        Returns:
            Whether manual review is required
        """
        if not self.ontology:
            return True

        et = self.ontology.get_entity_type(entity_type)
        if not et or not et.merge_strategy:
            return True

        # High confidence matches may not require review
        if confidence >= 0.95 and not et.merge_strategy.require_manual_review:
            return False

        return et.merge_strategy.require_manual_review

    def propose_relationships_from_correlation(
        self,
        table: str,
        from_column: str,
        to_column: str,
        relationship_type: str,
        source_entity_type: Optional[str] = None,
        target_entity_type: Optional[str] = None,
        min_co_occurrence: int = 2,
    ) -> List[Dict[str, Any]]:
        """Generate relationship proposals from correlated data.

        Args:
            table: Source table
            from_column: Source entity column
            to_column: Target entity column
            relationship_type: Type of relationship (must be in ontology if ontology is set)
            source_entity_type: Type of source entity (for ontology validation)
            target_entity_type: Type of target entity (for ontology validation)
            min_co_occurrence: Minimum co-occurrence count

        Returns:
            List of proposed relationship additions
        """
        # Validate relationship type against ontology
        if self.ontology and source_entity_type and target_entity_type:
            is_valid, errors = self.ontology.validate_relationship(
                relationship_type, source_entity_type, target_entity_type
            )
            if not is_valid:
                logger.warning(
                    f"Relationship validation errors: {errors}. Proceeding anyway."
                )

        correlations = self.analysis.find_correlations(table, from_column, to_column)

        proposals = []
        for row in correlations:
            co_occurrence = row.get("co_occurrence_count", 0)

            if co_occurrence < min_co_occurrence:
                continue

            # Calculate confidence based on co-occurrence frequency
            confidence = min(100, 50 + (co_occurrence * 10))

            proposals.append(
                {
                    "type": "add_edge",
                    "from": str(row[from_column]),
                    "to": str(row[to_column]),
                    "relationship": relationship_type,
                    "properties": {
                        "co_occurrence_count": co_occurrence,
                        "source_table": table,
                        "from_column": from_column,
                        "to_column": to_column,
                    },
                    "evidence": f"Found {co_occurrence} co-occurrences in {table} between {from_column} and {to_column}",
                    "confidence": confidence,
                }
            )

        return proposals

    def propose_nodes_from_patterns(
        self,
        table: str,
        pattern_column: str,
        entity_type: str,
        min_frequency: int = 5,
    ) -> List[Dict[str, Any]]:
        """Generate node proposals from frequent patterns.

        Args:
            table: Source table
            pattern_column: Column to analyze for patterns
            entity_type: Type of entity to create
            min_frequency: Minimum pattern frequency

        Returns:
            List of proposed node additions
        """
        patterns = self.analysis.find_frequent_patterns(
            table, pattern_column, min_frequency
        )

        proposals = []
        for row in patterns:
            value = row.get("value")
            frequency = row.get("frequency", 0)

            if not value:
                continue

            # Confidence increases with frequency
            confidence = min(100, 60 + (frequency * 2))

            proposals.append(
                {
                    "type": "add_node",
                    "entity": entity_type,
                    "label": str(value),
                    "properties": {
                        "frequency": frequency,
                        "pattern_source": pattern_column,
                        "source_table": table,
                    },
                    "confidence": confidence,
                    "evidence": f"Frequent pattern in {table}.{pattern_column} (frequency: {frequency})",
                }
            )

        return proposals

    def propose_from_sql_query(
        self,
        query: str,
        entity_type: str,
        label_column: str,
        property_columns: Optional[List[str]] = None,
        confidence: int = 75,
    ) -> List[Dict[str, Any]]:
        """Generate node proposals from custom SQL query results.

        Args:
            query: SQL query to execute
            entity_type: Type of entity
            label_column: Column to use as node label
            property_columns: Columns to include as properties
            confidence: Base confidence score

        Returns:
            List of proposed node additions
        """
        results = self.db.execute_query(query)

        proposals = []
        for row in results:
            if label_column not in row:
                continue

            properties = {}
            if property_columns:
                for col in property_columns:
                    if col in row and row[col] is not None:
                        properties[col] = row[col]

            proposals.append(
                {
                    "type": "add_node",
                    "entity": entity_type,
                    "label": str(row[label_column]),
                    "properties": properties,
                    "confidence": confidence,
                    "evidence": f"Extracted from custom query",
                }
            )

        return proposals
