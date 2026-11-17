def generate_openapi_client_stub() -> str:
    return '''"""Auto stub: UDS sdk - не HTTP API."""

from sandbox.sdk_client import SandboxSdkClient


def client(socket_path: str) -> SandboxSdkClient:
    return SandboxSdkClient(socket_path)
'''
