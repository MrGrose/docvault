import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return probe.returncode == 0


def run_in_host(task: Path, env: dict[str, str]) -> int:
    return subprocess.run([sys.executable, str(task)], env=env, check=False).returncode


def run_in_sandbox(task: Path, socket_path: Path, env: dict[str, str]) -> int:
    from sandbox.docker_runtime import DockerRuntime

    subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(ROOT / "docker/sandbox.Dockerfile"),
            "-t",
            "docvault-sandbox:local",
            str(ROOT),
        ],
        check=True,
        capture_output=True,
    )
    runtime = DockerRuntime()
    result = runtime.run(
        image="docvault-sandbox:local",
        command=["python", "/work/task.py"],
        env=env,
        mounts={
            str(socket_path): "/run/broker.sock",
            str(task): "/work/task.py",
            str(ROOT / "src"): "/work/src",
        },
    )
    return result.exit_code


def main() -> int:
    from agent.pipeline import run_pipeline
    from broker.service import CapabilityBroker
    from broker.uds_server import UdsBrokerServer
    from core.capability.tokens import issue_token
    from core.repo import Repository

    repo_path = Path(os.environ.get("DOCVAULT_REPO", ROOT / "data/demo-agent"))
    socket_path = Path(os.environ.get("DOCVAULT_BROKER_SOCKET", ROOT / "data/broker.sock"))
    space = os.environ.get("DOCVAULT_SPACE", "default")
    secret = os.environ.get("DOCVAULT_CAPABILITY_SECRET", "dev-demo-secret")
    os.environ["DOCVAULT_CAPABILITY_SECRET"] = secret

    shutil.rmtree(repo_path, ignore_errors=True)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
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
        agent_id="demo-agent",
    )
    server = UdsBrokerServer(str(socket_path), CapabilityBroker(repo))
    server.start_background()
    time.sleep(0.2)

    task_dir = Path(tempfile.mkdtemp(prefix="docvault-demo-"))
    task = task_dir / "task.py"
    task.write_text(run_pipeline("update_tariffs"), encoding="utf-8")
    env = {
        "DOCVAULT_BROKER_SOCKET": "/run/broker.sock" if docker_ready() else str(socket_path),
        "DOCVAULT_CAPABILITY_TOKEN": token,
        "DOCVAULT_SPACE": space,
        "DOCVAULT_IDEM_KEY": os.environ.get("DOCVAULT_IDEM_KEY", "demo-agent-write-1"),
        "DOCVAULT_RUN_ID": run_id,
        "PYTHONPATH": "/work/src" if docker_ready() else str(ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    try:
        if docker_ready():
            print("runtime: docker")
            code = run_in_sandbox(task, socket_path, env)
        else:
            print("runtime: host")
            code = run_in_host(task, {**os.environ, **env})
    finally:
        server.stop()
        socket_path.unlink(missing_ok=True)
        shutil.rmtree(task_dir, ignore_errors=True)

    if code != 0:
        repo.close()
        print(f"agent exit: {code}")
        return code

    cs_id = repo.publish_draft(draft_id, None, "agent demo", "user:host", source="agent")
    tree = repo.tree_at(cs_id)
    repo.close()
    print(f"changeset: {cs_id}")
    print("files: " + ", ".join(sorted(tree)))
    print("demo-agent OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
