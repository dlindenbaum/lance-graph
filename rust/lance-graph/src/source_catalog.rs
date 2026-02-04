// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright The Lance Authors

//! Context-free source catalog for DataFusion logical planning.

use std::any::Any;
use std::collections::HashMap;
use std::sync::Arc;

use arrow_schema::{Schema, SchemaRef};
use datafusion::logical_expr::TableSource;

/// A minimal catalog to resolve node labels and relationship types to logical table sources.
pub trait GraphSourceCatalog: Send + Sync {
    fn node_source(&self, label: &str) -> Option<Arc<dyn TableSource>>;
    fn relationship_source(&self, rel_type: &str) -> Option<Arc<dyn TableSource>>;
}

/// A simple in-memory catalog useful for tests and bootstrap wiring.
pub struct InMemoryCatalog {
    node_sources: HashMap<String, Arc<dyn TableSource>>,
    rel_sources: HashMap<String, Arc<dyn TableSource>>,
}

impl InMemoryCatalog {
    pub fn new() -> Self {
        Self {
            node_sources: HashMap::new(),
            rel_sources: HashMap::new(),
        }
    }

    pub fn with_node_source(
        mut self,
        label: impl Into<String>,
        source: Arc<dyn TableSource>,
    ) -> Self {
        self.node_sources.insert(label.into(), source);
        self
    }

    pub fn with_relationship_source(
        mut self,
        rel_type: impl Into<String>,
        source: Arc<dyn TableSource>,
    ) -> Self {
        self.rel_sources.insert(rel_type.into(), source);
        self
    }
}

impl Default for InMemoryCatalog {
    fn default() -> Self {
        Self::new()
    }
}

impl GraphSourceCatalog for InMemoryCatalog {
    fn node_source(&self, label: &str) -> Option<Arc<dyn TableSource>> {
        self.node_sources.get(label).cloned()
    }

    fn relationship_source(&self, rel_type: &str) -> Option<Arc<dyn TableSource>> {
        self.rel_sources.get(rel_type).cloned()
    }
}

/// A trivial logical table source with a fixed schema.
pub struct SimpleTableSource {
    schema: SchemaRef,
}

impl SimpleTableSource {
    pub fn new(schema: SchemaRef) -> Self {
        Self { schema }
    }
    pub fn empty() -> Self {
        Self {
            schema: Arc::new(Schema::empty()),
        }
    }
}

impl TableSource for SimpleTableSource {
    fn as_any(&self) -> &dyn Any {
        self
    }
    fn schema(&self) -> SchemaRef {
        self.schema.clone()
    }
}

/// A catalog backed by Lance datasets with full predicate pushdown support.
///
/// This catalog wraps Lance datasets as DataFusion TableProviders, enabling
/// predicate pushdown all the way to the Lance storage layer. This is more
/// efficient than loading data into memory first.
///
/// # Example
///
/// ```ignore
/// use lance::dataset::Dataset;
/// use lance_graph::source_catalog::LanceCatalog;
///
/// let nodes_ds = Dataset::open("/path/to/nodes.lance").await?;
/// let rels_ds = Dataset::open("/path/to/relationships.lance").await?;
///
/// let catalog = LanceCatalog::new()
///     .with_node_dataset("nodes", nodes_ds)
///     .with_relationship_dataset("relationships", rels_ds);
/// ```
///
/// # Feature Flag
///
/// This type is only available when the `lance` feature is enabled:
/// ```toml
/// lance-graph = { version = "0.1", features = ["lance"] }
/// ```
#[cfg(feature = "lance")]
pub struct LanceCatalog {
    node_datasets: HashMap<String, Arc<lance::dataset::Dataset>>,
    rel_datasets: HashMap<String, Arc<lance::dataset::Dataset>>,
}

#[cfg(feature = "lance")]
impl LanceCatalog {
    pub fn new() -> Self {
        Self {
            node_datasets: HashMap::new(),
            rel_datasets: HashMap::new(),
        }
    }

    /// Add a Lance dataset as a node source.
    pub fn with_node_dataset(
        mut self,
        name: impl Into<String>,
        dataset: Arc<lance::dataset::Dataset>,
    ) -> Self {
        self.node_datasets.insert(name.into(), dataset);
        self
    }

    /// Add a Lance dataset as a relationship source.
    pub fn with_relationship_dataset(
        mut self,
        name: impl Into<String>,
        dataset: Arc<lance::dataset::Dataset>,
    ) -> Self {
        self.rel_datasets.insert(name.into(), dataset);
        self
    }
}

#[cfg(feature = "lance")]
impl Default for LanceCatalog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(feature = "lance")]
impl GraphSourceCatalog for LanceCatalog {
    fn node_source(&self, label: &str) -> Option<Arc<dyn TableSource>> {
        self.node_datasets
            .get(label)
            .map(|ds| Arc::clone(ds) as Arc<dyn TableSource>)
    }

    fn relationship_source(&self, rel_type: &str) -> Option<Arc<dyn TableSource>> {
        self.rel_datasets
            .get(rel_type)
            .map(|ds| Arc::clone(ds) as Arc<dyn TableSource>)
    }
}
