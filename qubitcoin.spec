# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Qubitcoin
Creates standalone binary executable
"""

block_cipher = None

a = Analysis(
    ['src/run_node.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'qubitcoin',
        'qubitcoin.database',
        'qubitcoin.quantum',
        'qubitcoin.consensus',
        'qubitcoin.mining',
        'qubitcoin.network',
        'qubitcoin.storage',
        'qubitcoin.utils',
        'sqlalchemy.dialects.postgresql',
        'sqlalchemy.dialects.postgresql.psycopg2',
        'psycopg2',
        'qiskit',
        'qiskit_aer',
        'qiskit.primitives',
        'fastapi',
        'uvicorn',
        'prometheus_client',
        'ipfshttpclient',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='qubitcoin-node',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
