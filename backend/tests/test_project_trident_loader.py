import asyncio
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.db.models import Case, DemoLoad, Statement
from app.demo.project_trident import PROJECT_TRIDENT_TAG, load_project_trident, reset_project_trident


def _session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "test_data" / "demo" / "project_trident"


def test_project_trident_loader_replaces_only_its_tagged_records(monkeypatch, tmp_path):
    # Keep uploads outside the repository during the integration-style service test.
    from app.api import routes_upload
    from app.demo import project_trident

    monkeypatch.setattr(routes_upload, "UPLOAD_DIR", tmp_path / "uploads")
    routes_upload.UPLOAD_DIR.mkdir()
    monkeypatch.setattr(project_trident, "UPLOAD_DIR", routes_upload.UPLOAD_DIR)

    db = _session()
    unrelated = Statement(filename_hash="unrelated", original_filename="unrelated.csv", status="uploaded")
    db.add(unrelated)
    db.commit()
    db.refresh(unrelated)

    first = asyncio.run(load_project_trident(db, _fixture_dir()))
    second = asyncio.run(load_project_trident(db, _fixture_dir()))

    assert first["verification"]["verified"] is True
    assert second["verification"]["verified"] is True
    assert second["statement_ids"] == first["statement_ids"]
    assert db.get(Statement, unrelated.id) is not None

    load = db.get(DemoLoad, PROJECT_TRIDENT_TAG)
    assert load and load.status == "ready"
    assert len(load.statement_ids) == 3
    assert len(db.exec(select(Case)).all()) == 1
    assert len(db.exec(select(Statement)).all()) == 4

    deleted = reset_project_trident(db)
    assert deleted == {"cases": 1, "statements": 3}
    assert db.get(DemoLoad, PROJECT_TRIDENT_TAG) is None
    assert db.get(Statement, unrelated.id) is not None
