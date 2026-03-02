# Validation scripts are standalone (python3 script.py), not pytest tests.
# They use module-level sys.exit() which crashes pytest collection.
# This conftest excludes them from pytest discovery.
collect_ignore = [
    "comprehensive_validation.py",
    "final_genesis_validation.py",
    "pre_genesis_validation.py",
    "ultimate_genesis_validation.py",
    "test_system.py",
]
