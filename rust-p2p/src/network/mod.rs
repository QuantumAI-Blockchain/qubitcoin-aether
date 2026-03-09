//! P2P network manager using latest libp2p 0.56

use libp2p::{
    gossipsub, mdns, identify, ping, kad,
    swarm::{NetworkBehaviour, Swarm, SwarmEvent, Config as SwarmConfig},
    PeerId, Multiaddr,
    SwarmBuilder,
};
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::sync::atomic::Ordering;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::mpsc;
use tracing::{info, warn, error, debug};

use crate::bridge::P2PStats;
use crate::protocol::{NetworkMessage, PeerInfo};

const PROTOCOL_VERSION: &str = "/qubitcoin/1.0.0";

#[derive(NetworkBehaviour)]
pub struct QubitcoinBehaviour {
    gossipsub: gossipsub::Behaviour,
    mdns: mdns::tokio::Behaviour,
    identify: identify::Behaviour,
    ping: ping::Behaviour,
    kad: kad::Behaviour<kad::store::MemoryStore>,
}

pub struct P2PNetwork {
    swarm: Swarm<QubitcoinBehaviour>,
    peers: HashMap<PeerId, PeerInfo>,
    /// Peers subscribed to QBC gossipsub topics (actual QBC nodes)
    qbc_peers: HashSet<PeerId>,
    to_python_tx: mpsc::UnboundedSender<NetworkMessage>,
    from_python_rx: mpsc::UnboundedReceiver<NetworkMessage>,
    stats: Arc<P2PStats>,
}

impl P2PNetwork {
    pub async fn new(
        port: u16,
        to_python_tx: mpsc::UnboundedSender<NetworkMessage>,
        from_python_rx: mpsc::UnboundedReceiver<NetworkMessage>,
        stats: Arc<P2PStats>,
    ) -> anyhow::Result<Self> {
        let local_key = libp2p::identity::Keypair::generate_ed25519();
        let local_peer_id = PeerId::from(local_key.public());
        
        info!("🦀 Local peer ID: {}", local_peer_id);
        
        // Maximum gossipsub message size: 10 MB.
        // This prevents OOM attacks from peers sending excessively large messages.
        // A typical QBC block is well under 5 MB (Dilithium sigs are ~3KB each,
        // with ~333 tx/MB → a full 5 MB block is ~1,665 transactions).
        const MAX_GOSSIPSUB_MESSAGE_SIZE: usize = 10 * 1024 * 1024; // 10 MB

        let gossipsub_config = gossipsub::ConfigBuilder::default()
            .heartbeat_interval(Duration::from_secs(1))
            .validation_mode(gossipsub::ValidationMode::Strict)
            .max_transmit_size(MAX_GOSSIPSUB_MESSAGE_SIZE)
            .message_id_fn(|message| {
                use sha2::{Sha256, Digest};
                let mut hasher = Sha256::new();
                hasher.update(&message.data);
                gossipsub::MessageId::from(hasher.finalize().to_vec())
            })
            .build()
            .map_err(|e| anyhow::anyhow!("Gossipsub config: {}", e))?;
        
        let mut gossipsub = gossipsub::Behaviour::new(
            gossipsub::MessageAuthenticity::Signed(local_key.clone()),
            gossipsub_config,
        )
        .map_err(|e| anyhow::anyhow!("Gossipsub creation: {}", e))?;
        
        let block_topic = gossipsub::IdentTopic::new("qubitcoin-blocks");
        let tx_topic = gossipsub::IdentTopic::new("qubitcoin-transactions");
        
        gossipsub.subscribe(&block_topic)?;
        gossipsub.subscribe(&tx_topic)?;
        
        info!("📡 Subscribed to gossipsub topics");
        
        let identify = identify::Behaviour::new(
            identify::Config::new(PROTOCOL_VERSION.to_string(), local_key.public())
                .with_agent_version("qubitcoin-p2p/1.0.0".to_string())
        );
        
        let ping = ping::Behaviour::new(
            ping::Config::new()
                .with_interval(Duration::from_secs(30))
                .with_timeout(Duration::from_secs(10))
        );
        
        let store = kad::store::MemoryStore::new(local_peer_id);
        let kad = kad::Behaviour::new(local_peer_id, store);
        
        let mdns = mdns::tokio::Behaviour::new(
            mdns::Config::default(),
            local_peer_id,
        )?;
        
        let behaviour = QubitcoinBehaviour {
            gossipsub,
            mdns,
            identify,
            ping,
            kad,
        };
        
        let swarm = SwarmBuilder::with_existing_identity(local_key)
            .with_tokio()
            .with_tcp(
                libp2p::tcp::Config::default(),
                libp2p::noise::Config::new,
                libp2p::yamux::Config::default,
            )?
            .with_quic()
            .with_dns()?
            .with_relay_client(libp2p::noise::Config::new, libp2p::yamux::Config::default)?
            .with_behaviour(|_key, _relay| Ok(behaviour))?
            .with_swarm_config(|cfg: SwarmConfig| {
                cfg.with_idle_connection_timeout(Duration::from_secs(60))
            })
            .build();
        
        let mut swarm_instance = swarm;
        
        let tcp_addr: Multiaddr = format!("/ip4/0.0.0.0/tcp/{}", port).parse()?;
        let quic_addr: Multiaddr = format!("/ip4/0.0.0.0/udp/{}/quic-v1", port + 1).parse()?;
        
        swarm_instance.listen_on(tcp_addr)?;
        swarm_instance.listen_on(quic_addr)?;
        
        info!("🌐 P2P listening on TCP:{} + QUIC:{}", port, port + 1);

        // Dial seed peers from PEER_SEEDS env var (comma-separated multiaddrs)
        // Example: /ip4/152.42.215.182/tcp/4002,/ip4/1.2.3.4/tcp/4002
        if let Ok(seeds) = std::env::var("PEER_SEEDS") {
            let seeds = seeds.trim();
            if !seeds.is_empty() {
                for seed in seeds.split(',') {
                    let seed = seed.trim();
                    if seed.is_empty() { continue; }
                    match seed.parse::<Multiaddr>() {
                        Ok(addr) => {
                            info!("🌱 Dialing seed peer: {}", addr);
                            if let Err(e) = swarm_instance.dial(addr.clone()) {
                                warn!("Failed to dial seed {}: {}", addr, e);
                            }
                        }
                        Err(e) => {
                            warn!("Invalid seed multiaddr '{}': {}", seed, e);
                        }
                    }
                }
            }
        }

        Ok(Self {
            swarm: swarm_instance,
            peers: HashMap::new(),
            qbc_peers: HashSet::new(),
            to_python_tx,
            from_python_rx,
            stats,
        })
    }
    
    pub async fn run(mut self) {
        use futures::StreamExt;

        info!("🚀 P2P network running with libp2p 0.56");

        loop {
            tokio::select! {
                biased;
                Some(msg) = self.from_python_rx.recv() => {
                    debug!("📤 From Python: {}", msg);
                    self.broadcast_message(msg);
                }
                event = self.swarm.select_next_some() => {
                    self.handle_swarm_event(event);
                }
            }
            // Yield to tokio runtime so gRPC server can process requests
            tokio::task::yield_now().await;
        }
    }
    
    fn handle_swarm_event(&mut self, event: SwarmEvent<QubitcoinBehaviourEvent>) {
        match event {
            SwarmEvent::NewListenAddr { address, .. } => {
                info!("📍 Listening on {}", address);
            }
            
            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Mdns(mdns::Event::Discovered(peers))) => {
                for (peer_id, multiaddr) in peers {
                    info!("🔍 mDNS discovered: {} at {}", peer_id, multiaddr);
                    
                    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
                    self.peers.insert(peer_id, PeerInfo {
                        peer_id: peer_id.to_string(),
                        address: multiaddr.to_string(),
                        last_seen: now,
                    });
                    
                    self.swarm.behaviour_mut().kad.add_address(&peer_id, multiaddr.clone());
                    
                    if let Err(e) = self.swarm.dial(multiaddr) {
                        warn!("Failed to dial {}: {}", peer_id, e);
                    }
                }
            }
            
            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Mdns(mdns::Event::Expired(peers))) => {
                for (peer_id, _) in peers {
                    info!("❌ Peer expired: {}", peer_id);
                    self.peers.remove(&peer_id);
                }
            }
            
            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Identify(identify::Event::Received { peer_id, info, .. })) => {
                info!("📋 Identified peer {}: {:?}", peer_id, info.protocol_version);
                
                for addr in info.listen_addrs {
                    self.swarm.behaviour_mut().kad.add_address(&peer_id, addr);
                }
            }
            
            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Ping(ping::Event { peer, result, .. })) => {
                match result {
                    Ok(rtt) => debug!("🏓 Ping to {}: {:?}", peer, rtt),
                    Err(e) => warn!("Ping failed to {}: {}", peer, e),
                }
            }
            
            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Gossipsub(gossipsub::Event::Message {
                propagation_source,
                message_id,
                message,
            })) => {
                debug!("📥 Gossipsub from {}: {:?}", propagation_source, message_id);
                self.handle_gossipsub_message(message);
            }

            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Gossipsub(gossipsub::Event::Subscribed {
                peer_id,
                topic,
            })) => {
                let topic_str = topic.as_str();
                if topic_str == "qubitcoin-blocks" || topic_str == "qubitcoin-transactions" {
                    if self.qbc_peers.insert(peer_id) {
                        self.stats.peer_count.store(self.qbc_peers.len(), Ordering::Relaxed);
                        info!("⛓️ QBC peer joined ({}): {} — QBC peers: {}", topic_str, peer_id, self.qbc_peers.len());
                    }
                }
            }

            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Gossipsub(gossipsub::Event::Unsubscribed {
                peer_id,
                topic,
            })) => {
                let topic_str = topic.as_str();
                if topic_str == "qubitcoin-blocks" || topic_str == "qubitcoin-transactions" {
                    // Only remove if not subscribed to ANY QBC topic
                    let still_on_blocks = topic_str != "qubitcoin-blocks" &&
                        self.swarm.behaviour().gossipsub.all_peers()
                            .any(|(p, topics)| *p == peer_id && topics.iter().any(|t| t.as_str() == "qubitcoin-blocks"));
                    let still_on_txs = topic_str != "qubitcoin-transactions" &&
                        self.swarm.behaviour().gossipsub.all_peers()
                            .any(|(p, topics)| *p == peer_id && topics.iter().any(|t| t.as_str() == "qubitcoin-transactions"));
                    if !still_on_blocks && !still_on_txs {
                        if self.qbc_peers.remove(&peer_id) {
                            self.stats.peer_count.store(self.qbc_peers.len(), Ordering::Relaxed);
                            info!("⛓️ QBC peer left: {} — QBC peers: {}", peer_id, self.qbc_peers.len());
                        }
                    }
                }
            }

            SwarmEvent::Behaviour(QubitcoinBehaviourEvent::Kad(event)) => {
                debug!("🗂️ Kademlia: {:?}", event);
            }

            SwarmEvent::ConnectionEstablished { peer_id, endpoint, .. } => {
                info!("✅ Connected to {}: {}", peer_id, endpoint.get_remote_address());
                let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
                self.peers.insert(peer_id, PeerInfo {
                    peer_id: peer_id.to_string(),
                    address: endpoint.get_remote_address().to_string(),
                    last_seen: now,
                });
                // Update gRPC-visible peer count from direct connections
                self.stats.peer_count.store(self.peers.len(), Ordering::Relaxed);
            }

            SwarmEvent::ConnectionClosed { peer_id, cause, .. } => {
                info!("❌ Disconnected from {}: {:?}", peer_id, cause);
                self.peers.remove(&peer_id);
                self.qbc_peers.remove(&peer_id);
                // Update gRPC-visible peer count from direct connections
                self.stats.peer_count.store(self.peers.len(), Ordering::Relaxed);
            }
            
            _ => {}
        }
    }
    
    fn handle_gossipsub_message(&self, message: gossipsub::Message) {
        // SECURITY [SUB-H5]: Defense-in-depth size check at the application layer.
        // Gossipsub already enforces MAX_GOSSIPSUB_MESSAGE_SIZE at the transport level,
        // but we verify again here to guard against any bypass or future misconfiguration.
        if message.data.len() > 10 * 1024 * 1024 {
            warn!(
                "Dropping oversized gossipsub message ({} bytes) from {:?}",
                message.data.len(),
                message.source
            );
            return;
        }

        match bincode::deserialize::<NetworkMessage>(&message.data) {
            Ok(msg) => {
                debug!("📥 Decoded: {}", msg);
                let _ = self.to_python_tx.send(msg);
            }
            Err(e) => {
                warn!("Failed to deserialize gossipsub message ({} bytes): {}", message.data.len(), e);
            }
        }
    }
    
    fn broadcast_message(&mut self, msg: NetworkMessage) {
        let topic = match &msg {
            NetworkMessage::NewBlock { .. } | NetworkMessage::Block(_) => {
                gossipsub::IdentTopic::new("qubitcoin-blocks")
            }
            NetworkMessage::NewTransaction(_) => {
                gossipsub::IdentTopic::new("qubitcoin-transactions")
            }
            _ => return,
        };
        
        if let Ok(data) = bincode::serialize(&msg) {
            if let Err(e) = self.swarm.behaviour_mut().gossipsub.publish(topic, data) {
                error!("Failed to publish: {}", e);
            } else {
                debug!("📡 Broadcast: {}", msg);
            }
        }
    }
    
    pub fn peer_count(&self) -> usize {
        self.peers.len()
    }
}
