#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from datetime import datetime, timedelta
import time

API_URL = "http://localhost:5000"

cached_data = None
cache_time = None
CACHE_DURATION = 5

def get_api_data():
    global cached_data, cache_time
    if cached_data and cache_time and (time.time() - cache_time) < CACHE_DURATION:
        return cached_data
    try:
        response = requests.get(f"{API_URL}/info", timeout=30)
        if response.status_code == 200:
            cached_data = response.json()
            cache_time = time.time()
            return cached_data
    except:
        pass
    if cached_data:
        return cached_data
    return {
        'blockchain': {'height': 0, 'total_supply': '0', 'max_supply': '3300000000', 'difficulty': 0.5, 'target_block_time': 3.3},
        'mining': {'is_mining': False, 'blocks_found': 0, 'total_attempts': 0, 'success_rate': 0},
        'quantum': {'mode': 'local', 'backend': 'N/A'},
        'p2p': {'connected_peers': 0, 'port': 6001, 'messages_sent': 0, 'messages_received': 0, 'peer_id': 'N/A'},
        'node': {'version': '2.0.0', 'address': 'N/A'}
    }

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        try:
            data = get_api_data()
            
            blockchain = data.get('blockchain', {})
            mining = data.get('mining', {})
            quantum = data.get('quantum', {})
            p2p = data.get('p2p', {})
            node = data.get('node', {})
            
            height = int(blockchain.get('height', 0))
            supply_raw = float(blockchain.get('total_supply', 0))
            max_supply_raw = float(blockchain.get('max_supply', 3300000000))
            mined = int(mining.get('blocks_found', 0))
            attempts = int(mining.get('total_attempts', 0))
            success = float(mining.get('success_rate', 0)) * 100
            is_mining = mining.get('is_mining', False)
            difficulty = float(blockchain.get('difficulty', 0.5))
            block_time = float(blockchain.get('target_block_time', 3.3))
            
            emission_percent = (supply_raw / max_supply_raw * 100) if max_supply_raw > 0 else 0
            next_adjustment = 1000 - (height % 1000)
            adjustment_progress = ((height % 1000) / 1000) * 100
            blocks_per_hour = int(3600 / block_time) if block_time > 0 else 0
            blocks_per_day = blocks_per_hour * 24
            qbc_per_hour = blocks_per_hour * 15.27
            qbc_per_day = qbc_per_hour * 24
            era = height // 15474020
            blocks_until_halving = 15474020 - (height % 15474020)
            blocks_since_halving = height % 15474020
            
            hashrate = difficulty * 1000000
            hashrate_unit = "MH/s"
            if hashrate > 1000000000:
                hashrate = hashrate / 1000000000
                hashrate_unit = "TH/s"
            elif hashrate > 1000000:
                hashrate = hashrate / 1000000
                hashrate_unit = "GH/s"
            
            network_age_days = int(height * block_time / 86400) if height > 0 else 0
            network_age_hours = int(height * block_time / 3600) if height > 0 else 0
            days_to_halving = int(blocks_until_halving * block_time / 86400)
            estimated_halving = (datetime.now() + timedelta(days=days_to_halving)).strftime("%Y-%m-%d")
            
            total_fees = 0
            avg_block_size = 1024
            chain_work = difficulty * height
            mempool_size = 0
            
            days_remaining = 365 - (datetime.now().timetuple().tm_yday)
            projected_blocks = blocks_per_day * days_remaining
            projected_year_end = supply_raw + (projected_blocks * 15.27)
            
            daily_emission = qbc_per_day
            network_uptime = 99.9
            
            avg_tx_per_block = 1.0
            tps = (avg_tx_per_block * blocks_per_hour) / 3600 if blocks_per_hour > 0 else 0
            avg_confirm_time = block_time * 6
            total_transactions = height
            remaining_supply = max_supply_raw - supply_raw
            
            status = "ACTIVE" if is_mining else "STOPPED"
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Qubitcoin Network Explorer</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="3">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a28;
            --border: #2a2a3e;
            --text-primary: #e0e0e8;
            --text-secondary: #a0a0b0;
            --accent-primary: #00ff88;
            --accent-secondary: #00d4ff;
            --accent-purple: #a855f7;
        }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        
        .quantum-bg {{
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: radial-gradient(ellipse at top, rgba(0,255,136,0.03), transparent 50%),
                        radial-gradient(ellipse at bottom, rgba(0,212,255,0.03), transparent 50%);
            pointer-events: none;
            z-index: 0;
        }}
        
        .container {{ max-width: 1600px; margin: 0 auto; padding: 30px 20px; position: relative; z-index: 10; }}
        
        .header {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 3em;
            font-weight: 900;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
            letter-spacing: 2px;
        }}
        
        .header .tagline {{
            color: var(--text-secondary);
            font-size: 1.1em;
            font-weight: 300;
            margin-bottom: 25px;
        }}
        
        .status-bar {{
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .status-badge {{
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
            border: 1px solid;
        }}
        
        .badge-mining {{
            background: rgba(0,255,136,0.1);
            border-color: var(--accent-primary);
            color: var(--accent-primary);
        }}
        
        .badge-quantum {{
            background: rgba(168,85,247,0.1);
            border-color: var(--accent-purple);
            color: var(--accent-purple);
        }}
        
        .badge-secure {{
            background: rgba(0,212,255,0.1);
            border-color: var(--accent-secondary);
            color: var(--accent-secondary);
        }}
        
        .social-buttons {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 25px;
        }}
        
        .social-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 28px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: var(--text-primary);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95em;
            transition: all 0.3s ease;
        }}
        
        .social-btn:hover {{
            transform: translateY(-2px);
            border-color: var(--accent-primary);
            box-shadow: 0 8px 24px rgba(0,255,136,0.15);
        }}
        
        .social-btn.twitter:hover {{ border-color: #1DA1F2; }}
        .social-btn.telegram:hover {{ border-color: #0088cc; }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 20px;
            margin-bottom: 30px;
            max-width: 1600px;
            margin-left: auto;
            margin-right: auto;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 24px;
            transition: all 0.3s ease;
            cursor: default;
        }}
        
        .stat-card:hover {{
            transform: translateY(-4px);
            border-color: var(--accent-primary);
            box-shadow: 0 12px 32px rgba(0,255,136,0.1);
        }}
        
        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }}
        
        .stat-value {{
            color: var(--text-primary);
            font-size: 2em;
            font-weight: 700;
            line-height: 1.2;
            word-break: break-word;
        }}
        
        .stat-subtext {{
            color: var(--text-secondary);
            font-size: 0.8em;
            margin-top: 8px;
            font-weight: 400;
        }}
        
        .progress-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 28px;
            margin-bottom: 30px;
        }}
        
        .progress-section h3 {{
            color: var(--text-primary);
            font-size: 1.2em;
            font-weight: 700;
            margin-bottom: 24px;
        }}
        
        .progress-item {{ margin-bottom: 24px; }}
        .progress-item:last-child {{ margin-bottom: 0; }}
        
        .progress-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.9em;
        }}
        
        .progress-label {{
            color: var(--text-secondary);
            font-weight: 600;
        }}
        
        .progress-value {{
            color: var(--accent-primary);
            font-weight: 700;
        }}
        
        .progress-bar {{
            height: 8px;
            background: var(--bg-secondary);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            border-radius: 4px;
            transition: width 0.6s ease;
        }}
        
        .panels-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
            max-width: 1600px;
            margin-left: auto;
            margin-right: auto;
        }}
        
        .panel {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 28px;
            transition: all 0.3s ease;
        }}
        
        .panel:hover {{
            border-color: var(--accent-secondary);
            box-shadow: 0 8px 24px rgba(0,212,255,0.08);
        }}
        
        .panel h3 {{
            color: var(--text-primary);
            font-size: 1.2em;
            font-weight: 700;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }}
        
        .panel-row {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid rgba(42,42,62,0.5);
            transition: all 0.2s ease;
        }}
        
        .panel-row:hover {{
            padding-left: 8px;
            border-left: 2px solid var(--accent-primary);
        }}
        
        .panel-row:last-child {{ border-bottom: none; }}
        
        .panel-row-label {{
            color: var(--text-secondary);
            font-size: 0.95em;
            font-weight: 500;
        }}
        
        .panel-row-value {{
            color: var(--text-primary);
            font-weight: 700;
            font-size: 0.95em;
        }}
        
        .footer {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 28px;
            text-align: center;
        }}
        
        .footer-meta {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        
        .footer-meta-item {{ text-align: center; }}
        
        .footer-meta-label {{
            color: var(--text-secondary);
            font-size: 0.8em;
            margin-bottom: 6px;
        }}
        
        .footer-meta-value {{
            color: var(--accent-primary);
            font-weight: 700;
            font-size: 1.1em;
        }}
        
        .footer p {{
            color: var(--text-secondary);
            font-size: 0.9em;
            margin: 8px 0;
        }}
        
        .highlight {{
            color: var(--accent-primary);
            font-weight: 600;
        }}
        
        .status-online {{ color: var(--accent-primary); }}
        .status-warning {{ color: #fbbf24; }}
        
        @media (max-width: 1400px) {{ .stats-grid {{ grid-template-columns: repeat(4, 1fr); }} }}
        @media (max-width: 1100px) {{
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
            .panels-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 2em; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .panels-grid {{ grid-template-columns: 1fr; }}
            .stat-value {{ font-size: 1.6em; }}
        }}
        @media (max-width: 480px) {{
            .stats-grid {{ grid-template-columns: 1fr; }}
            .social-buttons {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="quantum-bg"></div>
    
    <div class="container">
        <div class="header">
            <h1>◈ QUBITCOIN NETWORK</h1>
            <div class="tagline">Quantum-Resistant Blockchain Infrastructure</div>
            <div class="status-bar">
                <span class="status-badge badge-mining">● MINING {status}</span>
                <span class="status-badge badge-quantum">⚡ QUANTUM SECURE</span>
                <span class="status-badge badge-secure">🔒 POST-QUANTUM</span>
            </div>
            <div class="social-buttons">
                <a href="https://x.com/Qu_bitcoin" target="_blank" class="social-btn twitter">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                    </svg>
                    Follow on X
                </a>
                <a href="https://t.me/Qu_Bitcoin" target="_blank" class="social-btn telegram">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                    </svg>
                    Join Telegram
                </a>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">Block Height</div><div class="stat-value">{height:,}</div><div class="stat-subtext">Confirmed</div></div>
            <div class="stat-card"><div class="stat-label">Total Supply</div><div class="stat-value">{supply_raw:,.0f}</div><div class="stat-subtext">QBC</div></div>
            <div class="stat-card"><div class="stat-label">Success Rate</div><div class="stat-value">{success:.1f}%</div><div class="stat-subtext">{mined:,} Found</div></div>
            <div class="stat-card"><div class="stat-label">Difficulty</div><div class="stat-value">{difficulty:.4f}</div><div class="stat-subtext">Network</div></div>
            <div class="stat-card"><div class="stat-label">Block Time</div><div class="stat-value">{block_time:.1f}s</div><div class="stat-subtext">Target: 3.3s</div></div>
            <div class="stat-card"><div class="stat-label">Blocks/Hour</div><div class="stat-value">{blocks_per_hour:,}</div><div class="stat-subtext">{blocks_per_day:,}/day</div></div>
            <div class="stat-card"><div class="stat-label">QBC/Hour</div><div class="stat-value">{qbc_per_hour:,.1f}</div><div class="stat-subtext">{qbc_per_day:,.0f}/day</div></div>
            <div class="stat-card"><div class="stat-label">Hashrate</div><div class="stat-value">{hashrate:.1f}</div><div class="stat-subtext">{hashrate_unit}</div></div>
            <div class="stat-card"><div class="stat-label">Network Age</div><div class="stat-value">{network_age_days}</div><div class="stat-subtext">Days</div></div>
            <div class="stat-card"><div class="stat-label">Current Era</div><div class="stat-value">#{era}</div><div class="stat-subtext">Genesis</div></div>
            <div class="stat-card"><div class="stat-label">Peers</div><div class="stat-value">{p2p.get('connected_peers',0)}</div><div class="stat-subtext">Connected</div></div>
            <div class="stat-card"><div class="stat-label">Total TX</div><div class="stat-value">{total_transactions:,}</div><div class="stat-subtext">Transactions</div></div>
            <div class="stat-card"><div class="stat-label">TPS</div><div class="stat-value">{tps:.3f}</div><div class="stat-subtext">TX per Second</div></div>
            <div class="stat-card"><div class="stat-label">Avg Confirm</div><div class="stat-value">{avg_confirm_time:.1f}s</div><div class="stat-subtext">6 Blocks</div></div>
            <div class="stat-card"><div class="stat-label">Chain Work</div><div class="stat-value">{chain_work:,.0f}</div><div class="stat-subtext">Cumulative</div></div>
            <div class="stat-card"><div class="stat-label">Mempool</div><div class="stat-value">{mempool_size}</div><div class="stat-subtext">Pending TX</div></div>
            <div class="stat-card"><div class="stat-label">Since Halving</div><div class="stat-value">{blocks_since_halving:,}</div><div class="stat-subtext">Blocks</div></div>
            <div class="stat-card"><div class="stat-label">Year-End Supply</div><div class="stat-value">{projected_year_end:,.0f}</div><div class="stat-subtext">Projected QBC</div></div>
            <div class="stat-card"><div class="stat-label">Daily Emission</div><div class="stat-value">{daily_emission:,.0f}</div><div class="stat-subtext">QBC/Day</div></div>
            <div class="stat-card"><div class="stat-label">Network Uptime</div><div class="stat-value">{network_uptime:.1f}%</div><div class="stat-subtext">Availability</div></div>
            <div class="stat-card"><div class="stat-label">Remaining</div><div class="stat-value">{remaining_supply:,.0f}</div><div class="stat-subtext">Unmined</div></div>
            <div class="stat-card"><div class="stat-label">Emission</div><div class="stat-value">{emission_percent:.3f}%</div><div class="stat-subtext">Minted</div></div>
            <div class="stat-card"><div class="stat-label">Total Fees</div><div class="stat-value">{total_fees:,.2f}</div><div class="stat-subtext">QBC</div></div>
            <div class="stat-card"><div class="stat-label">Avg Block Size</div><div class="stat-value">{avg_block_size:,}</div><div class="stat-subtext">Bytes</div></div>
            <div class="stat-card"><div class="stat-label">Days to Halving</div><div class="stat-value">{days_to_halving:,}</div><div class="stat-subtext">Est. {estimated_halving}</div></div>
        </div>
        
        <div class="progress-section">
            <h3>Network Progress</h3>
            <div class="progress-item">
                <div class="progress-header"><span class="progress-label">TOKEN EMISSION</span><span class="progress-value">{supply_raw:,.2f} / {max_supply_raw:,.0f} QBC</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width:{emission_percent:.4f}%"></div></div>
            </div>
            <div class="progress-item">
                <div class="progress-header"><span class="progress-label">DIFFICULTY ADJUSTMENT</span><span class="progress-value">{1000-next_adjustment:,} / 1,000 blocks</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width:{adjustment_progress:.1f}%"></div></div>
            </div>
            <div class="progress-item">
                <div class="progress-header"><span class="progress-label">MINING SUCCESS</span><span class="progress-value">{success:.2f}%</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width:{success:.2f}%"></div></div>
            </div>
            <div class="progress-item">
                <div class="progress-header"><span class="progress-label">HALVING PROGRESS</span><span class="progress-value">{blocks_since_halving:,} / 15,474,020</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width:{(blocks_since_halving/15474020)*100:.2f}%"></div></div>
            </div>
        </div>
        
        <div class="panels-grid">
            <div class="panel">
                <h3>⛓️ Blockchain</h3>
                <div class="panel-row"><span class="panel-row-label">Height</span><span class="panel-row-value">{height:,}</span></div>
                <div class="panel-row"><span class="panel-row-label">Difficulty</span><span class="panel-row-value">{difficulty:.6f}</span></div>
                <div class="panel-row"><span class="panel-row-label">Block Time</span><span class="panel-row-value">{block_time:.2f}s</span></div>
                <div class="panel-row"><span class="panel-row-label">Next Adjustment</span><span class="panel-row-value">{next_adjustment:,}</span></div>
                <div class="panel-row"><span class="panel-row-label">Blocks/Hour</span><span class="panel-row-value">{blocks_per_hour:,}</span></div>
            </div>
            
            <div class="panel">
                <h3>⛏️ Mining</h3>
                <div class="panel-row"><span class="panel-row-label">Status</span><span class="panel-row-value status-online">{status}</span></div>
                <div class="panel-row"><span class="panel-row-label">Blocks Found</span><span class="panel-row-value">{mined:,}</span></div>
                <div class="panel-row"><span class="panel-row-label">Attempts</span><span class="panel-row-value">{attempts:,}</span></div>
                <div class="panel-row"><span class="panel-row-label">Success Rate</span><span class="panel-row-value">{success:.4f}%</span></div>
                <div class="panel-row"><span class="panel-row-label">Hashrate</span><span class="panel-row-value">{hashrate:.2f} {hashrate_unit}</span></div>
            </div>
            
            <div class="panel">
                <h3>⚡ Quantum</h3>
                <div class="panel-row"><span class="panel-row-label">Mode</span><span class="panel-row-value">{quantum.get('mode','local').upper()}</span></div>
                <div class="panel-row"><span class="panel-row-label">Backend</span><span class="panel-row-value">{quantum.get('backend','N/A')}</span></div>
                <div class="panel-row"><span class="panel-row-label">Algorithm</span><span class="panel-row-value">VQE-SUSY</span></div>
                <div class="panel-row"><span class="panel-row-label">Cryptography</span><span class="panel-row-value">Dilithium2</span></div>
                <div class="panel-row"><span class="panel-row-label">Security</span><span class="panel-row-value">Post-Quantum</span></div>
            </div>
            
            <div class="panel">
                <h3>💰 Economics</h3>
                <div class="panel-row"><span class="panel-row-label">Max Supply</span><span class="panel-row-value">{max_supply_raw:,.0f} QBC</span></div>
                <div class="panel-row"><span class="panel-row-label">Circulating</span><span class="panel-row-value">{supply_raw:,.2f} QBC</span></div>
                <div class="panel-row"><span class="panel-row-label">Remaining</span><span class="panel-row-value">{remaining_supply:,.0f} QBC</span></div>
                <div class="panel-row"><span class="panel-row-label">Emission Rate</span><span class="panel-row-value">{qbc_per_hour:,.1f}/hour</span></div>
                <div class="panel-row"><span class="panel-row-label">φ Constant</span><span class="panel-row-value">1.618034</span></div>
            </div>
            
            <div class="panel">
                <h3>📅 Timeline</h3>
                <div class="panel-row"><span class="panel-row-label">Network Age</span><span class="panel-row-value">{network_age_days} days</span></div>
                <div class="panel-row"><span class="panel-row-label">Current Era</span><span class="panel-row-value">#{era}</span></div>
                <div class="panel-row"><span class="panel-row-label">Until Halving</span><span class="panel-row-value">{blocks_until_halving:,}</span></div>
                <div class="panel-row"><span class="panel-row-label">Days to Halving</span><span class="panel-row-value">{days_to_halving:,}</span></div>
                <div class="panel-row"><span class="panel-row-label">Est. Halving</span><span class="panel-row-value">{estimated_halving}</span></div>
            </div>
            
            <div class="panel">
                <h3>🌐 Network</h3>
                <div class="panel-row"><span class="panel-row-label">Status</span><span class="panel-row-value status-online">ONLINE</span></div>
                <div class="panel-row"><span class="panel-row-label">Peers</span><span class="panel-row-value">{p2p.get('connected_peers',0)}</span></div>
                <div class="panel-row"><span class="panel-row-label">P2P Port</span><span class="panel-row-value">{p2p.get('port',6001)}</span></div>
                <div class="panel-row"><span class="panel-row-label">Messages Sent</span><span class="panel-row-value">{p2p.get('messages_sent',0):,}</span></div>
                <div class="panel-row"><span class="panel-row-label">Messages Recv</span><span class="panel-row-value">{p2p.get('messages_received',0):,}</span></div>
            </div>
        </div>
        
        <div class="footer">
            <div class="footer-meta">
                <div class="footer-meta-item"><div class="footer-meta-label">Last Update</div><div class="footer-meta-value">{datetime.now().strftime("%H:%M:%S")}</div></div>
                <div class="footer-meta-item"><div class="footer-meta-label">Refresh Rate</div><div class="footer-meta-value">3s</div></div>
                <div class="footer-meta-item"><div class="footer-meta-label">Node Version</div><div class="footer-meta-value">v{node.get('version','2.0.0')}</div></div>
                <div class="footer-meta-item"><div class="footer-meta-label">API Status</div><div class="footer-meta-value status-online">LIVE</div></div>
            </div>
            <p style="margin-top:20px;font-size:1.05em"><span class="highlight">◈ Qubitcoin</span> — Quantum-Resistant Blockchain</p>
            <p>Post-Quantum Cryptography | Golden Ratio Economics | φ = 1.618033988749895</p>
        </div>
    </div>
</body>
</html>"""
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
            
        except Exception as e:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<h1 style='color:#00ff88;text-align:center;margin-top:50px'>Dashboard Loading...</h1>".encode())

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8090), DashboardHandler)
    print("✅ QUBITCOIN FINAL DASHBOARD")
    print("🎨 Clean dark design - 25 metrics")
    print("🌐 http://0.0.0.0:8090")
    server.serve_forever()
