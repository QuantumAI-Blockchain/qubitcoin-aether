"""Basic tests for Qubitcoin node"""
import requests
import time

BASE_URL = "http://localhost:5000"

def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print(f"✓ Health check: {response.json()}")
    assert response.status_code == 200

def test_chain_info():
    """Test chain info"""
    response = requests.get(f"{BASE_URL}/chain/info")
    print(f"✓ Chain info: {response.json()}")
    assert response.status_code == 200

def test_balance():
    """Test balance query"""
    response = requests.get(f"{BASE_URL}/")
    root_data = response.json()
    address = root_data['address']
    
    response = requests.get(f"{BASE_URL}/balance/{address}")
    print(f"✓ Balance: {response.json()}")
    assert response.status_code == 200

def test_mining():
    """Test mining endpoints"""
    # Get current stats
    response = requests.get(f"{BASE_URL}/mining/stats")
    print(f"✓ Mining stats: {response.json()}")
    
    # Stop mining
    response = requests.post(f"{BASE_URL}/mining/stop")
    print(f"✓ Stop mining: {response.json()}")
    
    time.sleep(2)
    
    # Start mining
    response = requests.post(f"{BASE_URL}/mining/start")
    print(f"✓ Start mining: {response.json()}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Running Qubitcoin Node Tests")
    print("="*60 + "\n")
    
    test_health()
    test_chain_info()
    test_balance()
    test_mining()
    
    print("\n" + "="*60)
    print("✓ All tests passed!")
    print("="*60 + "\n")
