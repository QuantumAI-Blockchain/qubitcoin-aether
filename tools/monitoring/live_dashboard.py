#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════╗
║         QUBITCOIN ULTIMATE LIVE BLOCKCHAIN EXPLORER          ║
║              Production-Grade Terminal Dashboard              ║
╚═══════════════════════════════════════════════════════════════╝
"""

import requests
import time
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich import box
from rich.align import Align
from datetime import datetime
import re

console = Console()
RPC_URL = "http://localhost:5000"

# State tracking
last_height = 0
height_history = []
blocks_per_minute = 0

def parse_prometheus_metrics(text):
    """Parse Prometheus metrics into dict"""
    metrics = {}
    for line in text.split('\n'):
        if line.startswith('#') or not line.strip():
            continue
        match = re.match(r'([a-z_]+)(?:\{([^}]*)\})?\s+(.+)', line)
        if match:
            name, labels, value = match.groups()
            try:
                metrics[name] = float(value)
            except:
                metrics[name] = value
    return metrics

def get_prometheus_metrics():
    """Get Prometheus metrics"""
    try:
        r = requests.get(f"{RPC_URL}/metrics", timeout=2)
        if r.ok:
            return parse_prometheus_metrics(r.text)
    except:
        pass
    return {}

def get_info():
    """Get node info from /info endpoint"""
    try:
        r = requests.get(f"{RPC_URL}/info", timeout=2)
        if r.ok:
            return r.json()
    except:
        pass
    return None

def calculate_blocks_per_minute(current_height):
    """Calculate mining rate"""
    global last_height, height_history, blocks_per_minute
    
    now = time.time()
    
    if current_height > last_height:
        height_history.append((now, current_height))
        last_height = current_height
    
    # Keep last 60 seconds
    height_history[:] = [(t, h) for t, h in height_history if now - t < 60]
    
    if len(height_history) >= 2:
        time_span = height_history[-1][0] - height_history[0][0]
        block_span = height_history[-1][1] - height_history[0][1]
        if time_span > 0:
            blocks_per_minute = (block_span / time_span) * 60
    
    return blocks_per_minute

def make_epic_header():
    """Massive QUBITCOIN header"""
    header = Text()
    header.append("╔" + "═"*125 + "╗\n", style="bold bright_cyan")
    header.append("║", style="bold bright_cyan")
    header.append(" "*125, style="on blue")
    header.append("║\n", style="bold bright_cyan")
    
    header.append("║", style="bold bright_cyan")
    header.append(" "*10, style="on blue")
    header.append("⚛️  Q U B I T C O I N    L I V E    B L O C K C H A I N    E X P L O R E R  ⚛️", style="bold white on blue")
    header.append(" "*10, style="on blue")
    header.append("║\n", style="bold bright_cyan")
    
    header.append("║", style="bold bright_cyan")
    header.append(" "*125, style="on blue")
    header.append("║\n", style="bold bright_cyan")
    
    header.append("╠" + "═"*125 + "╣\n", style="bold bright_cyan")
    header.append("║", style="bold bright_cyan")
    header.append("       🔐 Quantum-Resistant Blockchain       │       ⚛️  Proof-of-SUSY-Alignment       │       💎 Golden Ratio Economics (φ = 1.618)      ".ljust(125), style="dim cyan")
    header.append("║\n", style="bold bright_cyan")
    header.append("╚" + "═"*125 + "╝", style="bold bright_cyan")
    
    return Panel(header, box=box.HEAVY, border_style="bright_cyan", padding=(0, 0))

def make_live_stats(info, metrics):
    """Live statistics banner"""
    if not info:
        return Panel("🔴 CONNECTING TO NODE...", style="red bold", box=box.HEAVY)
    
    blockchain = info.get('blockchain', {})
    mining = info.get('mining', {})
    
    height = blockchain.get('height', 0)
    supply = blockchain.get('total_supply', '0')
    if isinstance(supply, str):
        try:
            supply = float(supply)
        except:
            supply = 0
    
    blocks_found = mining.get('blocks_found', 0)
    success_rate = mining.get('success_rate', 0) * 100
    
    bpm = calculate_blocks_per_minute(height)
    
    # Create live stats table
    table = Table.grid(padding=2)
    table.add_column(style="cyan bold", justify="center")
    table.add_column(style="cyan bold", justify="center")
    table.add_column(style="cyan bold", justify="center")
    table.add_column(style="cyan bold", justify="center")
    table.add_column(style="cyan bold", justify="center")
    
    # Headers
    headers = Table.grid()
    headers.add_column(justify="center")
    headers.add_row(Text("⛓️  BLOCK HEIGHT", style="dim"))
    
    values = Table.grid()
    values.add_column(justify="center")
    values.add_row(Text(f"{height:,}", style="green bold"))
    
    col1 = Table.grid()
    col1.add_row(headers)
    col1.add_row(values)
    
    # Supply
    h2 = Table.grid()
    h2.add_column(justify="center")
    h2.add_row(Text("💰 TOTAL SUPPLY", style="dim"))
    
    v2 = Table.grid()
    v2.add_column(justify="center")
    v2.add_row(Text(f"{supply:,.2f} QBC", style="yellow bold"))
    
    col2 = Table.grid()
    col2.add_row(h2)
    col2.add_row(v2)
    
    # Mining rate
    h3 = Table.grid()
    h3.add_column(justify="center")
    h3.add_row(Text("⚡ MINING RATE", style="dim"))
    
    v3 = Table.grid()
    v3.add_column(justify="center")
    rate_color = "green" if bpm > 10 else "yellow" if bpm > 1 else "red"
    v3.add_row(Text(f"{bpm:.2f} blk/min", style=f"{rate_color} bold"))
    
    col3 = Table.grid()
    col3.add_row(h3)
    col3.add_row(v3)
    
    # Blocks mined
    h4 = Table.grid()
    h4.add_column(justify="center")
    h4.add_row(Text("⛏️  BLOCKS MINED", style="dim"))
    
    v4 = Table.grid()
    v4.add_column(justify="center")
    v4.add_row(Text(f"{blocks_found:,}", style="magenta bold"))
    
    col4 = Table.grid()
    col4.add_row(h4)
    col4.add_row(v4)
    
    # Success rate
    h5 = Table.grid()
    h5.add_column(justify="center")
    h5.add_row(Text("🎯 SUCCESS RATE", style="dim"))
    
    v5 = Table.grid()
    v5.add_column(justify="center")
    v5.add_row(Text(f"{success_rate:.2f}%", style="cyan bold"))
    
    col5 = Table.grid()
    col5.add_row(h5)
    col5.add_row(v5)
    
    table.add_row(col1, col2, col3, col4, col5)
    
    return Panel(
        table,
        title="[bold green]🔥 LIVE STATISTICS 🔥",
        border_style="green",
        box=box.DOUBLE,
        padding=(1, 2)
    )

def make_blockchain_panel(info):
    """Blockchain details"""
    if not info:
        return Panel("Loading...", title="⛓️  Blockchain")
    
    blockchain = info.get('blockchain', {})
    
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="cyan", justify="right", ratio=1)
    table.add_column(style="white bold", justify="left", ratio=2)
    
    height = blockchain.get('height', 0)
    difficulty = blockchain.get('difficulty', 0)
    block_time = blockchain.get('target_block_time', 3.3)
    
    table.add_row("⛓️  Height:", f"{height:,} blocks")
    table.add_row("📊 Difficulty:", f"{difficulty:.6f}")
    table.add_row("⏱️  Block Time:", f"{block_time}s (target)")
    table.add_row("🔄 Era:", "#0 (Genesis)")
    
    # Calculate blocks per day
    blocks_per_day = (86400 / block_time)
    table.add_row("📅 Daily Rate:", f"~{blocks_per_day:,.0f} blocks")
    
    # Uptime estimate
    uptime_days = height * block_time / 86400
    table.add_row("⏰ Chain Age:", f"~{uptime_days:.2f} days")
    
    return Panel(
        table,
        title="[bold blue]⛓️  Blockchain",
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 1)
    )

def make_mining_panel(info, metrics):
    """Mining statistics"""
    if not info:
        return Panel("Loading...", title="⛏️  Mining")
    
    mining = info.get('mining', {})
    
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="yellow", justify="right", ratio=1)
    table.add_column(style="green bold", justify="left", ratio=2)
    
    is_mining = mining.get('is_mining', False)
    status = "🟢 ACTIVE" if is_mining else "🔴 STOPPED"
    table.add_row("Status:", status)
    
    blocks_found = mining.get('blocks_found', 0)
    attempts = mining.get('total_attempts', 0)
    success_rate = mining.get('success_rate', 0) * 100
    
    table.add_row("⛏️  Blocks Found:", f"{blocks_found:,}")
    table.add_row("🎲 Total Attempts:", f"{attempts:,}")
    table.add_row("🎯 Success Rate:", f"{success_rate:.2f}%")
    
    # Prometheus metrics
    qbc_mined = metrics.get('qbc_blocks_mined_total', 0)
    table.add_row("📊 Confirmed:", f"{int(qbc_mined):,}")
    
    # Calculate hashrate equivalent
    bpm = blocks_per_minute
    if bpm > 0:
        hashrate = bpm * 50  # 50 VQE iters per block
        table.add_row("⚡ VQE Rate:", f"{hashrate:.1f} iter/min")
    
    return Panel(
        table,
        title="[bold yellow]⛏️  Mining Engine",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(1, 1)
    )

def make_quantum_panel(info):
    """Quantum engine"""
    if not info:
        return Panel("Loading...", title="⚛️  Quantum")
    
    quantum = info.get('quantum', {})
    
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="magenta", justify="right", ratio=1)
    table.add_column(style="cyan bold", justify="left", ratio=2)
    
    mode = quantum.get('mode', 'unknown')
    backend = quantum.get('backend', 'unknown')
    
    table.add_row("⚛️  Mode:", mode.upper())
    table.add_row("🖥️  Backend:", backend)
    table.add_row("🔐 Crypto:", "Dilithium2 (PQC)")
    table.add_row("🧮 Algorithm:", "VQE-SUSY")
    table.add_row("🎲 Qubits:", "4-qubit system")
    table.add_row("📐 Ansatz:", "TwoLocal (RY+CZ)")
    table.add_row("🔬 Iterations:", "50 per block")
    table.add_row("⚡ Optimizer:", "COBYLA")
    
    return Panel(
        table,
        title="[bold magenta]⚛️  Quantum Engine",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(1, 1)
    )

def make_economics_panel(info):
    """Economics & tokenomics"""
    if not info:
        return Panel("Loading...", title="💰 Economics")
    
    blockchain = info.get('blockchain', {})
    emission = blockchain.get('emission', {})
    
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="yellow", justify="right", ratio=1)
    table.add_column(style="green bold", justify="left", ratio=2)
    
    max_supply = emission.get('supply_cap', 3300000000)
    total_supply = emission.get('total_supply', 0)
    
    table.add_row("📊 Model:", "SUSY Economics")
    table.add_row("🎯 Max Supply:", f"{max_supply:,.0f} QBC")
    table.add_row("💰 Circulating:", f"{total_supply:,.2f} QBC")
    
    percent = (total_supply / max_supply) * 100
    table.add_row("📈 Emitted:", f"{percent:.4f}%")
    
    table.add_row("💎 Block Reward:", "15.27 QBC")
    table.add_row("⏱️  Block Time:", "3.3 seconds")
    table.add_row("🌟 Golden Ratio:", "φ = 1.618...")
    table.add_row("🔄 Halving:", "15.47M blocks")
    table.add_row("📅 Emission:", "33 years")
    
    return Panel(
        table,
        title="[bold yellow]💰 Economics",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(1, 1)
    )

def make_network_panel(info):
    """Network & P2P"""
    if not info:
        return Panel("Loading...", title="🌐 Network")
    
    p2p = info.get('p2p', {})
    
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="cyan", justify="right", ratio=1)
    table.add_column(style="white bold", justify="left", ratio=2)
    
    peers = p2p.get('connected_peers', 0)
    max_peers = p2p.get('max_peers', 50)
    port = p2p.get('port', 6001)
    peer_id = p2p.get('peer_id', 'N/A')
    
    status = "🟢 SOLO MODE" if peers == 0 else f"🟢 {peers} PEERS"
    table.add_row("Status:", status)
    
    table.add_row("👥 Connected:", f"{peers} / {max_peers}")
    table.add_row("🔌 Port:", str(port))
    table.add_row("🆔 Peer ID:", peer_id)
    
    msgs_sent = p2p.get('messages_sent', 0)
    msgs_recv = p2p.get('messages_received', 0)
    
    table.add_row("📤 Msgs Sent:", f"{msgs_sent:,}")
    table.add_row("📥 Msgs Recv:", f"{msgs_recv:,}")
    
    return Panel(
        table,
        title="[bold cyan]🌐 P2P Network",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 1)
    )

def make_node_panel(info):
    """Node information"""
    if not info:
        return Panel("Offline", title="🖥️  Node", border_style="red")
    
    node = info.get('node', {})
    
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="dim", justify="right", ratio=1)
    table.add_column(style="white", justify="left", ratio=2)
    
    version = node.get('version', 'N/A')
    address = node.get('address', 'N/A')
    
    table.add_row("Version:", f"v{version}")
    table.add_row("Network:", "MAINNET")
    
    addr_short = address[:16] + "..." if len(address) > 16 else address
    table.add_row("Address:", addr_short)
    
    table.add_row("Status:", "🟢 ONLINE")
    
    return Panel(
        table,
        title="[bold white]🖥️  Node Info",
        border_style="white",
        box=box.ROUNDED,
        padding=(1, 1)
    )

def make_emission_progress(info):
    """Emission progress bar"""
    if not info:
        return Panel("Loading...", title="📊 Emission")
    
    blockchain = info.get('blockchain', {})
    emission = blockchain.get('emission', {})
    
    total_supply = emission.get('total_supply', 0)
    max_supply = emission.get('supply_cap', 3300000000)
    
    percent = (total_supply / max_supply) * 100
    
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Supply Emission Progress:"),
        BarColumn(bar_width=50, complete_style="green", finished_style="bright_green"),
        TextColumn("[progress.percentage]{task.percentage:>6.4f}%"),
        TextColumn(f"[dim]({total_supply:,.2f} / {max_supply:,.0f} QBC)"),
        expand=True
    )
    
    task = progress.add_task("emission", total=100, completed=percent)
    
    return Panel(
        progress,
        title="[bold green]📊 Token Emission",
        border_style="green",
        box=box.DOUBLE,
        padding=(1, 2)
    )

def make_system_metrics(metrics):
    """System performance metrics"""
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="dim", justify="right", ratio=1)
    table.add_column(style="green", justify="left", ratio=2)
    
    cpu = metrics.get('process_cpu_seconds_total', 0)
    mem = metrics.get('process_resident_memory_bytes', 0) / 1024 / 1024  # MB
    fds = metrics.get('process_open_fds', 0)
    
    table.add_row("💻 CPU Time:", f"{cpu:.2f}s")
    table.add_row("🧠 Memory:", f"{mem:.0f} MB")
    table.add_row("📁 Open FDs:", f"{int(fds)}")
    
    return Panel(
        table,
        title="[bold green]⚙️  System",
        border_style="green",
        box=box.ROUNDED,
        padding=(1, 1)
    )

def make_footer():
    """Live footer"""
    now = datetime.now()
    
    footer = Table.grid(expand=True)
    footer.add_column(justify="left", ratio=1)
    footer.add_column(justify="center", ratio=1)
    footer.add_column(justify="right", ratio=1)
    
    footer.add_row(
        Text("🔄 Auto-refresh: 1.5s", style="dim"),
        Text(now.strftime("⏰ %Y-%m-%d %H:%M:%S"), style="cyan bold"),
        Text("Press Ctrl+C to exit", style="dim italic")
    )
    
    return Panel(footer, box=box.SIMPLE, border_style="dim")

def make_dashboard():
    """Build dashboard layout"""
    layout = Layout()
    
    layout.split(
        Layout(name="header", size=7),
        Layout(name="stats", size=8),
        Layout(name="top_row", size=14),
        Layout(name="mid_row", size=14),
        Layout(name="bottom", size=6),
        Layout(name="footer", size=3)
    )
    
    # Top row
    layout["top_row"].split_row(
        Layout(name="blockchain"),
        Layout(name="mining"),
        Layout(name="quantum")
    )
    
    # Mid row
    layout["mid_row"].split_row(
        Layout(name="economics"),
        Layout(name="network"),
        Layout(name="node"),
        Layout(name="system")
    )
    
    return layout

def update_dashboard(layout):
    """Update all panels"""
    info = get_info()
    metrics = get_prometheus_metrics()
    
    layout["header"].update(make_epic_header())
    layout["stats"].update(make_live_stats(info, metrics))
    layout["blockchain"].update(make_blockchain_panel(info))
    layout["mining"].update(make_mining_panel(info, metrics))
    layout["quantum"].update(make_quantum_panel(info))
    layout["economics"].update(make_economics_panel(info))
    layout["network"].update(make_network_panel(info))
    layout["node"].update(make_node_panel(info))
    layout["system"].update(make_system_metrics(metrics))
    layout["bottom"].update(make_emission_progress(info))
    layout["footer"].update(make_footer())

def main():
    """Run the ultimate dashboard"""
    console.clear()
    
    with console.status("[bold cyan]Initializing Qubitcoin Explorer...", spinner="dots"):
        time.sleep(1)
    
    console.print("\n[bold green]✓[/] Dashboard loaded!\n")
    time.sleep(0.5)
    
    layout = make_dashboard()
    
    try:
        with Live(layout, refresh_per_second=2, screen=True) as live:
            while True:
                update_dashboard(layout)
                time.sleep(1.5)
    except KeyboardInterrupt:
        console.clear()
        console.print("\n[bold yellow]⚡ Dashboard stopped[/]\n")
        console.print("[bold cyan]Thank you for using Qubitcoin Explorer![/]\n")

if __name__ == "__main__":
    main()
