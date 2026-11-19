import os
import shutil
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    import docker
    from agent.pipeline import run_pipeline
    from broker.service import CapabilityBroker
    from broker.uds_server import UdsBrokerServer
    from core.capability.tokens import issue_token
    from core.repo import Repository
    from sandbox.docker_runtime import DockerRuntime

    repo_path = Path(os.environ.get("DOCVAULT_REPO", "/app/data/repo"))
    socket_path = Path(os.environ.get("DOCVAULT_BROKER_SOCKET", "/run/broker.sock"))
    work_dir = Path(os.environ.get("DOCVAULT_WORK_DIR", "/work"))
    work_volume = os.environ.get("DOCVAULT_WORK_VOLUME", "docvault-work")
    broker_volume = os.environ.get("DOCVAULT_BROKER_VOLUME", "docvault-broker")
    space = os.environ.get("DOCVAULT_SPACE", "default")
    os.environ.setdefault("DOCVAULT_CAPABILITY_SECRET", "dev-demo-secret")
    os.environ.setdefault("DOCVAULT_BROKER_SOCKET_MODE", "660")

    shutil.rmtree(repo_path, ignore_errors=True)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    socket_path.unlink(missing_ok=True)
    repo = Repository.init(repo_path)
    draft = repo.drafts.create(space, "user:host", repo.pointers.head(space))
    draft_id = str(draft["id"])
    print(f"draft: {draft_id}")

    run_id = uuid.uuid4().hex
    token = issue_token(
        space=space,
        path_prefixes=["docs/"],
        ops=["write_doc", "ping"],
        draft_id=draft_id,
        run_id=run_id,
        agent_id="compose-demo",
    )
    server = UdsBrokerServer(str(socket_path), CapabilityBroker(repo))
    server.start_background()
    time.sleep(0.2)

    task = work_dir / "task.py"
    task.write_text(run_pipeline("update_tariffs"), encoding="utf-8")
    client = docker.from_env()
    client.images.build(
        path=str(ROOT),
        dockerfile="docker/sandbox.Dockerfile",
        tag="docvault-sandbox:local",
        rm=True,
    )
    env = {
        "DOCVAULT_BROKER_SOCKET": "/run/broker.sock",
        "DOCVAULT_CAPABILITY_TOKEN": token,
        "DOCVAULT_SPACE": space,
        "DOCVAULT_IDEM_KEY": "compose-demo-1",
        "DOCVAULT_RUN_ID": run_id,
        "PYTHONPATH": "/opt",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        result = DockerRuntime().run(
            image="docvault-sandbox:local",
            command=["python", "/work/task.py"],
            env=env,
            mounts={},
            volume_mounts={work_volume: "/work", broker_volume: "/run"},
        )
    finally:
        server.stop()
        socket_path.unlink(missing_ok=True)

    if result.exit_code != 0:
        repo.close()
        print(f"agent exit: {result.exit_code}")
        return result.exit_code

    cs_id = repo.publish_draft(draft_id, None, "compose demo", "user:host", source="agent")
    tree = repo.tree_at(cs_id)
    repo.close()
    print(f"changeset: {cs_id}")
    print("files: " + ", ".join(sorted(tree)))
    print("compose demo OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
