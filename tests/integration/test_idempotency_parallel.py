from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def test_parallel_write_doc_one_effect(api: Any) -> None:
    draft = api.draft()
    headers = {"Idempotency-Key": "write-parallel"}

    def put_once() -> str:
        response = api.client.put(
            f"/changesets/{draft['id']}/doc/p.md",
            json={"content": "same"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return str(response.json()["blob_hash"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(put_once) for _ in range(8)]
        hashes = {f.result() for f in as_completed(futures)}
    assert len(hashes) == 1
