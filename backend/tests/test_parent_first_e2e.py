"""Exercise the public parent-first chain and the maintained smoke harness."""
import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.models.enums import LinkStatus, UserRole
from app.models.user import ParentStudentLink, User
from scripts.parent_first_smoke import run


@pytest.mark.parametrize("mode", ["flow", "dashboard", "application"])
def test_parent_registers_creates_student_student_rotates_password_parent_tracks(client, db, capsys, mode):
    run(client, mode)
    parent = db.scalar(select(User).where(User.role == UserRole.PARENT))
    children = list(db.scalars(select(User).where(User.role == UserRole.STUDENT).order_by(User.id)))
    assert len(children) == 2
    assert all(child.created_by_parent_id == parent.id for child in children)
    assert children[0].must_change_password is False and children[0].token_version == 1
    assert verify_password("Independent-smoke-password", children[0].password_hash)
    assert children[1].must_change_password is True and children[1].token_version == 0
    links = list(db.scalars(select(ParentStudentLink).order_by(ParentStudentLink.id)))
    assert [link.status for link in links] == [LinkStatus.REVOKED, LinkStatus.ACTIVE]
    assert all(link.activation_source == "parent_created" and link.confirmed_at is None for link in links)
    output = capsys.readouterr().out
    assert "Independent-smoke-password" not in output and "Temporary-smoke-password" not in output
    assert "access_token" not in output
