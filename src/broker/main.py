import argparse
import os
from pathlib import Path

from broker.service import CapabilityBroker
from broker.uds_server import UdsBrokerServer
from core.repo import Repository


def main() -> None:
    parser = argparse.ArgumentParser(description="DocVault capability broker (UDS)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="слушать Unix socket")
    sock_default = os.environ.get("DOCVAULT_BROKER_SOCKET", "data/broker.sock")
    serve.add_argument("--socket", default=sock_default)
    serve.add_argument("--repo", default=os.environ.get("DOCVAULT_REPO", "data/repo"))
    args = parser.parse_args()

    if args.cmd == "serve":
        repo_path = Path(args.repo)
        if not (repo_path / ".docvault").exists():
            Repository.init(repo_path)
        repo = Repository.open(repo_path)
        broker = CapabilityBroker(repo)
        UdsBrokerServer(args.socket, broker).serve_forever()


if __name__ == "__main__":
    main()
