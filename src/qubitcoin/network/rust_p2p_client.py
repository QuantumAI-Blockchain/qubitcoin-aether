"""
Python gRPC client for Rust P2P network
Bridges Python blockchain with Rust libp2p networking
"""
import grpc
import sys
import os
from typing import Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Import generated protobuf files
try:
    # Add rust-p2p/src/bridge to Python path
    rust_p2p_path = os.path.join(os.path.dirname(__file__), '../../../rust-p2p/src/bridge')
    if rust_p2p_path not in sys.path:
        sys.path.insert(0, rust_p2p_path)
    
    import p2p_service_pb2
    import p2p_service_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError as e:
    logger.warning(f"gRPC proto files not available: {e}")
    p2p_service_pb2 = None
    p2p_service_pb2_grpc = None
    GRPC_AVAILABLE = False


class RustP2PClient:
    """
    Client for Rust P2P network via gRPC
    Handles block/transaction broadcasting and peer statistics
    """
    
    def __init__(self, grpc_addr: str = "127.0.0.1:50051"):
        """
        Initialize gRPC client
        
        Args:
            grpc_addr: Address of Rust P2P gRPC server
        """
        self.grpc_addr = grpc_addr
        self.channel: Optional[grpc.Channel] = None
        self.stub = None
        self.connected = False
        
        if not GRPC_AVAILABLE:
            logger.warning("⚠️  gRPC not available - Rust P2P client disabled")
        
    def connect(self) -> bool:
        """
        Connect to Rust P2P gRPC server
        
        Returns:
            True if connected successfully
        """
        if not GRPC_AVAILABLE:
            logger.error("gRPC proto not available - cannot connect")
            return False
            
        try:
            self.channel = grpc.insecure_channel(self.grpc_addr)
            self.stub = p2p_service_pb2_grpc.P2PStub(self.channel)
            
            # Test connection
            stats = self.get_peer_stats()
            if stats is not None:
                self.connected = True
                logger.info(f"✅ Connected to Rust P2P at {self.grpc_addr}")
                logger.info(f"📊 Current peers: {stats.get('peer_count', 0)}")
                return True
            else:
                logger.error(f"Failed to get stats from Rust P2P")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Rust P2P: {e}")
            self.connected = False
            return False
    
    def broadcast_block(self, height: int, block_hash: str) -> bool:
        """
        Broadcast new block to P2P network
        
        Args:
            height: Block height
            block_hash: Block hash
            
        Returns:
            True if broadcast successful
        """
        if not self.connected or not self.stub:
            logger.warning("Not connected to Rust P2P - cannot broadcast block")
            return False
            
        try:
            request = p2p_service_pb2.BroadcastRequest(
                height=height,
                hash=block_hash
            )
            
            response = self.stub.BroadcastBlock(request, timeout=5.0)
            
            if response.success:
                logger.info(f"📡 Block {height} broadcasted via Rust P2P")
                return True
            else:
                logger.warning(f"Block broadcast failed")
                return False
                
        except grpc.RpcError as e:
            logger.error(f"gRPC error broadcasting block: {e.code()}: {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Error broadcasting block: {e}")
            return False
    
    def get_peer_stats(self) -> Optional[dict]:
        """
        Get current P2P network statistics
        
        Returns:
            Dict with peer_count and other stats, or None if failed
        """
        if not self.stub:
            return None
            
        try:
            request = p2p_service_pb2.PeerStatsRequest()
            response = self.stub.GetPeerStats(request, timeout=5.0)
            
            return {
                'peer_count': response.peer_count,
                'connected': True
            }
            
        except Exception as e:
            logger.debug(f"Failed to get peer stats: {e}")
            return None
    
    def get_peer_count(self) -> int:
        """
        Get number of connected peers
        
        Returns:
            Number of peers, or 0 if failed
        """
        stats = self.get_peer_stats()
        return stats.get('peer_count', 0) if stats else 0
    
    def disconnect(self):
        """Close gRPC connection"""
        if self.channel:
            self.channel.close()
            self.connected = False
            logger.info("Disconnected from Rust P2P")
