import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine

from app.api.routes_cases import CaseCreateIn, CaseUpdateIn, node_transactions
from app.db.models import Case, CaseAccountNode


def test_case_name_is_trimmed_and_blank_names_are_rejected():
    assert CaseCreateIn(name="  Project Trident  ").name == "Project Trident"
    assert CaseUpdateIn(name="  Renamed case ").name == "Renamed case"

    with pytest.raises(ValidationError):
        CaseCreateIn(name=" \t\n ")
    with pytest.raises(ValidationError):
        CaseUpdateIn(name="   ")


def test_node_transactions_rejects_node_owned_by_another_case():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        first_case = Case(name="First")
        second_case = Case(name="Second")
        db.add_all([first_case, second_case])
        db.flush()
        db.add(CaseAccountNode(
            id="second-case-node",
            case_id=second_case.id,
            kind="subject_account",
            label="Second case subject",
        ))
        db.commit()

        with pytest.raises(HTTPException) as exc:
            node_transactions(case_id=first_case.id, node_id="second-case-node", db=db)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Node not found"
