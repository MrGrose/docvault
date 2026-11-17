def draft_tariffs_code() -> str:
    return """import os
from sandbox.sdk_client import SandboxSdkClient

socket_path = os.environ["DOCVAULT_BROKER_SOCKET"]
token = os.environ["DOCVAULT_CAPABILITY_TOKEN"]
space = os.environ.get("DOCVAULT_SPACE", "default")
idem = os.environ.get("DOCVAULT_IDEM_KEY", "agent-tariffs-1")

client = SandboxSdkClient(socket_path)
client.write_doc(
    token=token,
    space=space,
    path="docs/tariffs.md",
    content="# Tariffs\\n\\nUpdated from agent demo.\\n",
    idempotency_key=idem,
)
"""
