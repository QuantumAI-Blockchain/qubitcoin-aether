"""FastAPI router for transaction reversibility endpoints.

These endpoints are mounted directly in rpc.py rather than as a separate router,
since they need access to the db_manager and reversibility_manager instances.
See network/rpc.py for the endpoint definitions.
"""

# All reversibility endpoints are defined inline in rpc.py's create_rpc_app()
# function, where they have direct access to the reversibility_manager and
# db_manager closures. This file exists as a placeholder for the module
# structure and for documentation purposes.
#
# Endpoints:
#   POST /reversal/request          - Request a reversal
#   POST /reversal/approve/{id}     - Guardian approves
#   GET  /reversal/status/{id}      - Check status
#   GET  /reversal/pending          - List pending reversals
#   POST /guardian/add              - Add a security guardian
#   DELETE /guardian/remove/{addr}  - Remove guardian
#   GET  /guardians                 - List all guardians
#   GET  /transaction/{txid}/window - Check reversal window
#   POST /transaction/set-window    - Set reversal window
