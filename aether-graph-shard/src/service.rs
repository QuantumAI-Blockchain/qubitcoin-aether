//! gRPC service implementation for the distributed graph shard.

use crate::router::ShardRouter;
use crate::storage::EdgeDirection;
use crate::types::{ShardEdge, ShardNode};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;
use tonic::{Request, Response, Status};
use tracing::warn;

pub mod proto {
    tonic::include_proto!("graph_shard");
}

use proto::graph_shard_service_server::GraphShardService;
use proto::*;

pub struct GraphShardServer {
    router: Arc<ShardRouter>,
}

impl GraphShardServer {
    pub fn new(router: Arc<ShardRouter>) -> Self {
        Self { router }
    }
}

// ── Conversion helpers ─────────────────────────────────────────────

fn node_to_proto(node: &ShardNode) -> NodeRecord {
    NodeRecord {
        node_id: node.node_id,
        node_type: node.node_type.clone(),
        content_hash: node.content_hash.clone(),
        content: node
            .content
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect(),
        confidence: node.confidence,
        source_block: node.source_block,
        timestamp: node.timestamp,
        domain: node.domain.clone(),
        last_referenced_block: node.last_referenced_block,
        reference_count: node.reference_count,
        grounding_source: node.grounding_source.clone(),
        edges_out: node.edges_out.clone(),
        edges_in: node.edges_in.clone(),
        embedding: node.embedding.clone().unwrap_or_default(),
    }
}

fn proto_to_node(record: &NodeRecord) -> ShardNode {
    let mut node = ShardNode {
        node_id: record.node_id,
        node_type: record.node_type.clone(),
        content_hash: record.content_hash.clone(),
        content: record
            .content
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect(),
        confidence: record.confidence,
        source_block: record.source_block,
        timestamp: record.timestamp,
        domain: record.domain.clone(),
        last_referenced_block: record.last_referenced_block,
        reference_count: record.reference_count,
        grounding_source: record.grounding_source.clone(),
        edges_out: record.edges_out.clone(),
        edges_in: record.edges_in.clone(),
        embedding: if record.embedding.is_empty() {
            None
        } else {
            Some(record.embedding.clone())
        },
    };
    if node.content_hash.is_empty() {
        node.content_hash = node.compute_hash();
    }
    node
}

fn edge_to_proto(edge: &ShardEdge) -> EdgeRecord {
    EdgeRecord {
        from_node_id: edge.from_node_id,
        to_node_id: edge.to_node_id,
        edge_type: edge.edge_type.clone(),
        weight: edge.weight,
        timestamp: edge.timestamp,
    }
}

fn proto_to_edge(record: &EdgeRecord) -> ShardEdge {
    ShardEdge {
        from_node_id: record.from_node_id,
        to_node_id: record.to_node_id,
        edge_type: record.edge_type.clone(),
        weight: record.weight,
        timestamp: record.timestamp,
    }
}

#[tonic::async_trait]
impl GraphShardService for GraphShardServer {
    // ── Node Operations ────────────────────────────────────────────

    async fn put_node(
        &self,
        request: Request<PutNodeRequest>,
    ) -> Result<Response<PutNodeResponse>, Status> {
        let req = request.into_inner();
        let record = req
            .node
            .ok_or_else(|| Status::invalid_argument("node required"))?;
        let node = proto_to_node(&record);

        let shard_id = self
            .router
            .put_node(&node)
            .map_err(|e| Status::internal(format!("put_node failed: {}", e)))?;

        Ok(Response::new(PutNodeResponse {
            node_id: node.node_id,
            shard_id,
            merkle_proof: String::new(),
        }))
    }

    async fn get_node(
        &self,
        request: Request<GetNodeRequest>,
    ) -> Result<Response<GetNodeResponse>, Status> {
        let req = request.into_inner();
        let result = self
            .router
            .get_node_any(req.node_id)
            .map_err(|e| Status::internal(format!("get_node failed: {}", e)))?;

        match result {
            Some(node) => Ok(Response::new(GetNodeResponse {
                node: Some(node_to_proto(&node)),
                found: true,
                shard_id: self.router.route(&node.domain, node.node_id),
            })),
            None => Ok(Response::new(GetNodeResponse {
                node: None,
                found: false,
                shard_id: 0,
            })),
        }
    }

    async fn get_nodes(
        &self,
        request: Request<GetNodesRequest>,
    ) -> Result<Response<GetNodesResponse>, Status> {
        let req = request.into_inner();
        let mut found_nodes = Vec::new();
        let mut missing = Vec::new();

        for id in &req.node_ids {
            match self.router.get_node_any(*id) {
                Ok(Some(node)) => found_nodes.push(node_to_proto(&node)),
                Ok(None) => missing.push(*id),
                Err(e) => {
                    warn!(node_id = id, error = %e, "Failed to get node");
                    missing.push(*id);
                }
            }
        }

        Ok(Response::new(GetNodesResponse {
            nodes: found_nodes,
            missing_ids: missing,
        }))
    }

    async fn delete_node(
        &self,
        request: Request<DeleteNodeRequest>,
    ) -> Result<Response<DeleteNodeResponse>, Status> {
        let req = request.into_inner();

        let node = self
            .router
            .get_node_any(req.node_id)
            .map_err(|e| Status::internal(e.to_string()))?;

        let (deleted, edges_removed) = if let Some(n) = node {
            self.router
                .delete_node(&n.domain, req.node_id, req.cascade_edges)
                .map_err(|e| Status::internal(e.to_string()))?
        } else {
            (false, 0)
        };

        Ok(Response::new(DeleteNodeResponse {
            deleted,
            edges_removed,
        }))
    }

    async fn update_confidence(
        &self,
        request: Request<UpdateConfidenceRequest>,
    ) -> Result<Response<UpdateConfidenceResponse>, Status> {
        let req = request.into_inner();

        let node = self
            .router
            .get_node_any(req.node_id)
            .map_err(|e| Status::internal(e.to_string()))?;

        if let Some(n) = node {
            let shard_id = self.router.route(&n.domain, req.node_id);
            if let Some(shard) = self.router.get_shard(shard_id) {
                let old = shard
                    .update_confidence(req.node_id, req.new_confidence, req.block_height)
                    .map_err(|e| Status::internal(e.to_string()))?;

                return Ok(Response::new(UpdateConfidenceResponse {
                    updated: old.is_some(),
                    old_confidence: old.unwrap_or(0.0),
                }));
            }
        }

        Ok(Response::new(UpdateConfidenceResponse {
            updated: false,
            old_confidence: 0.0,
        }))
    }

    // ── Edge Operations ────────────────────────────────────────────

    async fn put_edge(
        &self,
        request: Request<PutEdgeRequest>,
    ) -> Result<Response<PutEdgeResponse>, Status> {
        let req = request.into_inner();
        let record = req
            .edge
            .ok_or_else(|| Status::invalid_argument("edge required"))?;
        let edge = proto_to_edge(&record);

        let source_domain = match self.router.get_node_any(edge.from_node_id) {
            Ok(Some(n)) => n.domain.clone(),
            _ => "general".to_string(),
        };

        let created = self
            .router
            .put_edge(&edge, &source_domain)
            .map_err(|e| Status::internal(e.to_string()))?;

        Ok(Response::new(PutEdgeResponse {
            created,
            updated: !created,
        }))
    }

    async fn get_edges(
        &self,
        request: Request<GetEdgesRequest>,
    ) -> Result<Response<GetEdgesResponse>, Status> {
        let req = request.into_inner();
        let direction = match req.direction {
            0 => EdgeDirection::Outgoing,
            1 => EdgeDirection::Incoming,
            _ => EdgeDirection::Both,
        };

        let filter = if req.edge_type_filter.is_empty() {
            None
        } else {
            Some(req.edge_type_filter.as_str())
        };

        let node = self
            .router
            .get_node_any(req.node_id)
            .map_err(|e| Status::internal(e.to_string()))?;

        let edges = if let Some(n) = node {
            let shard_id = self.router.route(&n.domain, req.node_id);
            if let Some(shard) = self.router.get_shard(shard_id) {
                shard
                    .get_edges(req.node_id, direction, filter)
                    .map_err(|e| Status::internal(e.to_string()))?
            } else {
                Vec::new()
            }
        } else {
            Vec::new()
        };

        Ok(Response::new(GetEdgesResponse {
            edges: edges.iter().map(edge_to_proto).collect(),
        }))
    }

    async fn get_neighbors(
        &self,
        request: Request<GetNeighborsRequest>,
    ) -> Result<Response<GetNeighborsResponse>, Status> {
        let req = request.into_inner();
        let max_hops = req.max_hops.min(5).max(1) as usize;
        let limit = req.limit.max(10) as usize;

        let mut visited = std::collections::HashSet::new();
        let mut queue = std::collections::VecDeque::new();
        let mut result_nodes = Vec::new();
        let mut result_edges = Vec::new();

        queue.push_back((req.node_id, 0usize));
        visited.insert(req.node_id);

        while let Some((current_id, depth)) = queue.pop_front() {
            if depth >= max_hops || result_nodes.len() >= limit {
                break;
            }

            if let Ok(Some(node)) = self.router.get_node_any(current_id) {
                let shard_id = self.router.route(&node.domain, current_id);
                if let Some(shard) = self.router.get_shard(shard_id) {
                    let filter = if req.edge_type_filter.is_empty() {
                        None
                    } else {
                        Some(req.edge_type_filter.as_str())
                    };

                    if let Ok(edges) =
                        shard.get_edges(current_id, EdgeDirection::Outgoing, filter)
                    {
                        for edge in &edges {
                            result_edges.push(edge_to_proto(edge));

                            if !visited.contains(&edge.to_node_id) {
                                visited.insert(edge.to_node_id);
                                if let Ok(Some(neighbor)) =
                                    self.router.get_node_any(edge.to_node_id)
                                {
                                    result_nodes.push(node_to_proto(&neighbor));
                                    queue.push_back((edge.to_node_id, depth + 1));
                                }
                            }
                        }
                    }
                }
            }
        }

        result_nodes.truncate(limit);

        Ok(Response::new(GetNeighborsResponse {
            neighbors: result_nodes,
            paths: result_edges,
        }))
    }

    // ── Search ─────────────────────────────────────────────────────

    async fn search(
        &self,
        request: Request<SearchRequest>,
    ) -> Result<Response<SearchResponse>, Status> {
        let req = request.into_inner();
        let start = Instant::now();
        let top_k = req.top_k.max(1) as usize;

        let results = if req.domain_filter.is_empty() {
            self.router
                .search_all(&req.query, top_k, req.min_confidence)
        } else {
            self.router
                .search_domain(&req.domain_filter, &req.query, top_k, req.min_confidence)
        }
        .map_err(|e| Status::internal(e.to_string()))?;

        let total = results.len() as i64;

        Ok(Response::new(SearchResponse {
            results: results
                .into_iter()
                .map(|(node, score)| SearchResult {
                    node: Some(node_to_proto(&node)),
                    score,
                    match_type: "keyword".to_string(),
                })
                .collect(),
            total_candidates: total,
            latency_ms: start.elapsed().as_secs_f64() * 1000.0,
        }))
    }

    async fn vector_search(
        &self,
        _request: Request<VectorSearchRequest>,
    ) -> Result<Response<VectorSearchResponse>, Status> {
        Ok(Response::new(VectorSearchResponse {
            results: Vec::new(),
            latency_ms: 0.0,
        }))
    }

    async fn domain_search(
        &self,
        request: Request<DomainSearchRequest>,
    ) -> Result<Response<DomainSearchResponse>, Status> {
        let req = request.into_inner();
        let top_k = req.top_k.max(1) as usize;

        let results = self
            .router
            .search_domain(&req.domain, &req.query, top_k, req.min_confidence)
            .map_err(|e| Status::internal(e.to_string()))?;

        let stats = self.router.global_stats();
        let domain_count = stats
            .nodes_per_domain
            .get(&req.domain)
            .copied()
            .unwrap_or(0);

        Ok(Response::new(DomainSearchResponse {
            results: results
                .into_iter()
                .map(|(node, score)| SearchResult {
                    node: Some(node_to_proto(&node)),
                    score,
                    match_type: "keyword".to_string(),
                })
                .collect(),
            domain_node_count: domain_count,
        }))
    }

    async fn cross_domain_search(
        &self,
        request: Request<CrossDomainSearchRequest>,
    ) -> Result<Response<CrossDomainSearchResponse>, Status> {
        let req = request.into_inner();
        let start = Instant::now();
        let top_k = req.top_k_per_domain.max(1) as usize;

        let results = self
            .router
            .search_cross_domain(&req.domains, &req.query, top_k, req.min_confidence)
            .map_err(|e| Status::internal(e.to_string()))?;

        let mut per_domain = HashMap::new();
        let mut all_merged = Vec::new();

        for (domain, domain_results) in results {
            let proto_results: Vec<SearchResult> = domain_results
                .iter()
                .map(|(node, score)| SearchResult {
                    node: Some(node_to_proto(node)),
                    score: *score,
                    match_type: "keyword".to_string(),
                })
                .collect();

            if req.merge_results {
                all_merged.extend(proto_results.clone());
            }

            per_domain.insert(
                domain.clone(),
                DomainSearchResponse {
                    results: proto_results,
                    domain_node_count: 0,
                },
            );
        }

        all_merged.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        all_merged.truncate(top_k * req.domains.len());

        Ok(Response::new(CrossDomainSearchResponse {
            per_domain,
            merged: all_merged,
            total_latency_ms: start.elapsed().as_secs_f64() * 1000.0,
        }))
    }

    // ── Merkle ─────────────────────────────────────────────────────

    async fn get_merkle_root(
        &self,
        _request: Request<MerkleRootRequest>,
    ) -> Result<Response<MerkleRootResponse>, Status> {
        let start = Instant::now();
        let stats = self.router.global_stats();
        let root = self.router.global_merkle_root();

        Ok(Response::new(MerkleRootResponse {
            global_root: root,
            node_count: stats.total_nodes,
            compute_ms: start.elapsed().as_secs_f64() * 1000.0,
        }))
    }

    async fn get_shard_merkle_roots(
        &self,
        _request: Request<ShardMerkleRootsRequest>,
    ) -> Result<Response<ShardMerkleRootsResponse>, Status> {
        let roots: HashMap<u32, String> = self
            .router
            .shard_merkle_roots()
            .into_iter()
            .collect();
        let global = self.router.global_merkle_root();
        let stats = self.router.global_stats();

        Ok(Response::new(ShardMerkleRootsResponse {
            shard_roots: roots,
            global_root: global,
            total_nodes: stats.total_nodes,
        }))
    }

    // ── Statistics ─────────────────────────────────────────────────

    async fn get_stats(
        &self,
        _request: Request<StatsRequest>,
    ) -> Result<Response<StatsResponse>, Status> {
        let stats = self.router.global_stats();
        let total = stats.total_cache_hits + stats.total_cache_misses;
        let hit_rate = if total > 0 {
            stats.total_cache_hits as f64 / total as f64
        } else {
            0.0
        };

        Ok(Response::new(StatsResponse {
            total_nodes: stats.total_nodes,
            total_edges: stats.total_edges,
            nodes_per_domain: stats.nodes_per_domain.into_iter().collect(),
            nodes_per_type: stats.nodes_per_type.into_iter().collect(),
            edges_per_type: stats.edges_per_type.into_iter().collect(),
            avg_confidence: stats.avg_confidence,
            active_shards: stats.active_shards as i32,
            cache_hits: stats.total_cache_hits as i64,
            cache_misses: stats.total_cache_misses as i64,
            cache_hit_rate: hit_rate,
            merkle_root: stats.global_merkle_root,
        }))
    }

    async fn get_shard_stats(
        &self,
        request: Request<ShardStatsRequest>,
    ) -> Result<Response<ShardStatsResponse>, Status> {
        let req = request.into_inner();
        let stats = self
            .router
            .shard_stats(req.shard_id)
            .ok_or_else(|| Status::not_found("shard not found"))?;

        Ok(Response::new(ShardStatsResponse {
            shard_id: stats.shard_id,
            domain: stats.domain,
            node_count: stats.node_count,
            edge_count: stats.edge_count,
            disk_bytes: stats.disk_bytes as i64,
            avg_confidence: stats.avg_confidence,
            merkle_root: stats.merkle_root,
            last_compact_ms: 0.0,
        }))
    }

    async fn health_check(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthResponse>, Status> {
        let total = self.router.shard_count() as i32;
        let shard_health: HashMap<u32, bool> = (0..total as u32)
            .map(|i| (i, self.router.get_shard(i).is_some()))
            .collect();

        Ok(Response::new(HealthResponse {
            healthy: true,
            shards_online: total,
            shards_total: total,
            uptime_seconds: 0.0,
            shard_health,
        }))
    }

    // ── Bulk Operations ────────────────────────────────────────────

    async fn bulk_put_nodes(
        &self,
        request: Request<tonic::Streaming<PutNodeRequest>>,
    ) -> Result<Response<BulkPutResponse>, Status> {
        use tokio_stream::StreamExt;

        let mut stream = request.into_inner();
        let start = Instant::now();
        let mut written = 0i64;
        let mut errors = 0i64;

        while let Some(req) = stream.next().await {
            let req = req?;
            if let Some(record) = req.node {
                let node = proto_to_node(&record);
                match self.router.put_node(&node) {
                    Ok(_) => written += 1,
                    Err(e) => {
                        warn!(error = %e, node_id = node.node_id, "Bulk put node failed");
                        errors += 1;
                    }
                }
            }
        }

        Ok(Response::new(BulkPutResponse {
            nodes_written: written,
            edges_written: 0,
            errors,
            duration_ms: start.elapsed().as_secs_f64() * 1000.0,
        }))
    }

    async fn bulk_put_edges(
        &self,
        request: Request<tonic::Streaming<PutEdgeRequest>>,
    ) -> Result<Response<BulkPutResponse>, Status> {
        use tokio_stream::StreamExt;

        let mut stream = request.into_inner();
        let start = Instant::now();
        let mut written = 0i64;
        let mut errors = 0i64;

        while let Some(req) = stream.next().await {
            let req = req?;
            if let Some(record) = req.edge {
                let edge = proto_to_edge(&record);
                let domain = match self.router.get_node_any(edge.from_node_id) {
                    Ok(Some(n)) => n.domain.clone(),
                    _ => "general".to_string(),
                };
                match self.router.put_edge(&edge, &domain) {
                    Ok(_) => written += 1,
                    Err(e) => {
                        warn!(error = %e, "Bulk put edge failed");
                        errors += 1;
                    }
                }
            }
        }

        Ok(Response::new(BulkPutResponse {
            nodes_written: 0,
            edges_written: written,
            errors,
            duration_ms: start.elapsed().as_secs_f64() * 1000.0,
        }))
    }

    type StreamNodesStream = std::pin::Pin<
        Box<dyn futures::Stream<Item = Result<NodeRecord, Status>> + Send>,
    >;

    async fn stream_nodes(
        &self,
        request: Request<StreamNodesRequest>,
    ) -> Result<Response<Self::StreamNodesStream>, Status> {
        let req = request.into_inner();
        let batch_size = req.batch_size.max(100) as usize;

        let nodes = self
            .router
            .stream_nodes(&req.domain_filter, req.min_node_id, batch_size)
            .map_err(|e| Status::internal(e.to_string()))?;

        let stream =
            futures::stream::iter(nodes.into_iter().map(|n| Ok(node_to_proto(&n))));

        Ok(Response::new(Box::pin(stream)))
    }

    // ── Shard Management ───────────────────────────────────────────

    async fn rebalance_shards(
        &self,
        _request: Request<RebalanceRequest>,
    ) -> Result<Response<RebalanceResponse>, Status> {
        Ok(Response::new(RebalanceResponse {
            started: false,
            nodes_to_migrate: 0,
            estimated_seconds: 0.0,
        }))
    }

    async fn compact_shard(
        &self,
        request: Request<CompactRequest>,
    ) -> Result<Response<CompactResponse>, Status> {
        let req = request.into_inner();
        let min_score = if req.min_confidence > 0.0 {
            req.min_confidence
        } else {
            0.1
        };

        let (pruned, reclaimed) = if req.all_shards {
            self.router
                .compact_all(min_score, 0)
                .map_err(|e| Status::internal(e.to_string()))?
        } else if let Some(shard) = self.router.get_shard(req.shard_id) {
            shard
                .compact(min_score, 0)
                .map_err(|e| Status::internal(e.to_string()))?
        } else {
            return Err(Status::not_found("shard not found"));
        };

        Ok(Response::new(CompactResponse {
            nodes_pruned: pruned,
            bytes_reclaimed: reclaimed as i64,
            duration_ms: 0.0,
        }))
    }

    async fn get_shard_map(
        &self,
        _request: Request<ShardMapRequest>,
    ) -> Result<Response<ShardMapResponse>, Status> {
        let mut shards = HashMap::new();

        let stats = self.router.global_stats();
        for (domain, count) in &stats.nodes_per_domain {
            let d = crate::types::Domain::from_str(domain);
            let shard_id = d.shard_base_id() * 256;
            shards.insert(
                shard_id,
                ShardInfo {
                    shard_id,
                    domain: domain.clone(),
                    node_count: *count,
                    storage_path: format!("shard_{}_{}", domain, shard_id),
                    online: true,
                },
            );
        }

        Ok(Response::new(ShardMapResponse { shards }))
    }
}
