from __future__ import annotations

from leichtfacile.llm.client import Usage
from leichtfacile.schemas import Block, Draft, JobConfig
from leichtfacile.store import Store


def test_jobs_artifacts_and_usage(tmp_path) -> None:
    store = Store(tmp_path / "s.sqlite")
    job = store.create_job(JobConfig(level="B1"), title="Test")
    assert store.get_job(job.id).config.level == "B1"

    for version in (1, 2):
        draft = Draft(doc_id="d", lang="de", level="A2", version=version,
                      blocks=[Block(id="b001", kind="sentence",
                                    text=f"Version {version}.")])  # fmt: skip
        store.put_artifact(job.id, "draft", draft, version)
    assert store.versions(job.id, "draft") == [1, 2]
    assert store.get_artifact(job.id, "draft", Draft).version == 2
    assert store.get_artifact(job.id, "draft", Draft, version=1).blocks[0].text == "Version 1."
    assert store.get_artifact_json(job.id, "draft")["version"] == 2

    store.add_usage(job.id, Usage("write", "m", 10, 20, 300))
    store.update_job(job.id, status="running", stage="write")
    loaded = store.get_job(job.id)
    assert loaded.status == "running" and loaded.usage[0].tokens_out == 20
    assert [j.id for j in store.list_jobs()] == [job.id]

    assert store.delete_job(job.id)
    assert store.get_job(job.id) is None
    assert store.versions(job.id, "draft") == []  # artifacts go with the job
    store.close()
