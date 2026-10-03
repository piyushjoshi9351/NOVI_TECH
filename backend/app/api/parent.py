"""Parent-facing endpoints.

The ``/students/{student_id}/*`` router is constructed by ``parent_student_router()``
so the authorization dependency (``get_authorized_link``) can be attached at the
ROUTER level. That means no handler under it can be added without inheriting the
check -- the default-fastapi footgun of forgetting a dependency on one route is
removed by construction.

Two invariants worth stating out loud:

* **Authorization is one function.** ``get_authorized_link`` checks the parent
  role, an ACTIVE link, and that the student exists, is a student and is active.
  It raises 404 for anything else so student ids cannot be enumerated.
* **Consent is not an error.** A section the student has not shared comes back
  as ``null``/empty, never a 403, so the UI can render "<First name> hasn't
  shared this" and the rest of the dashboard still loads.

Every route that returns student data also sets ``Cache-Control: no-store``: these
are minors' data and must not sit in a shared cache. The single exception is
``/photo``, which uses ``private, max-age=300`` -- see its docstring.
"""

import base64
import binascii
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_parent, get_authorized_link
from app.models.user import User
from app.schemas.parent import (
    InsightsResponse,
    MemoryResponse,
    OverviewResponse,
    ParentLinkOut,
    ParentLinkCreated,
    ParentLinkList,
    ParentStudentRef,
    StudentLinkRequest,
)
from app.services import parent_insight, parent_links, parent_memory, parent_projection
from app.services.parent_links import GENERIC_INVITE_MESSAGE

logger = logging.getLogger("novi.parent_api")

router = APIRouter(prefix="/parent", tags=["parent"])

NO_STORE = {"Cache-Control": "no-store"}

# The subset of the data-URL types accepted on write (see
# `schemas.auth.validate_image_data_url`) that we will echo back as an image.
_PHOTO_MIME = re.compile(r"^data:(image/(?:png|jpeg|jpg|gif|webp));base64$")


@router.get("/students", response_model=ParentLinkList)
def list_my_students(
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Students this parent can currently see.

    Pending requests are listed too (so the UI can show "awaiting approval") but
    carry no student data -- the student hasn't consented, so there is nothing
    about them to return yet.
    """
    payload = [_link_out(link) for link in parent_links.links_for_parent(db, parent)]
    return {"links": payload}


@router.post("/links", response_model=ParentLinkCreated, status_code=201)
def request_link(
    data: StudentLinkRequest,
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Ask to follow a student.

    Always returns the same generic message whether or not the email belongs to
    an existing student, so this cannot be used to test whether an email is
    registered.
    """
    link = parent_links.create_pending_link(db, parent, data.student_email, label=data.label)
    return ParentLinkCreated(
        link_id=link.id,
        status=link.status.value,
        message=GENERIC_INVITE_MESSAGE,
    )


def _link_out(link) -> ParentLinkOut:
    """Serialize a link from the parent's view.

    A pending link's student details stay hidden: ``student`` is only populated
    once the link is ACTIVE.
    """
    is_active = getattr(link.status, "value", link.status) == "active"
    ref = None
    if is_active and link.student is not None:
        ref = ParentStudentRef(
            first_name=link.student.first_name or "",
            grade=link.student.grade,
        )
    return ParentLinkOut(
        id=link.id,
        status=getattr(link.status, "value", str(link.status)),
        label=link.label or "",
        scopes=link.scope_names,
        student=ref,
        # Same gate as `student`: only an active link discloses the id.
        student_id=link.student_id if (is_active and link.student is not None) else None,
        # Never echo the full invited address back to the requester.
        invited_email_first_name=(link.invited_email or "").split("@")[0] or None
        if link.student is None and link.invited_email
        else None,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


def _served(link) -> list[str]:
    return [s for s in parent_projection.SNAPSHOT_SECTIONS if link.has_scope(s)]


# --------------------------------------------------------------------------- scoped
def parent_student_router() -> APIRouter:
    """Build the per-student router with authorization attached router-wide."""
    scoped = APIRouter(
        prefix="/parent/students/{student_id}",
        tags=["parent"],
        dependencies=[Depends(get_authorized_link)],
        responses={404: {"description": "No active link to this student"}},
    )

    @scoped.get("/photo")
    def photo(
        resolved: tuple = Depends(get_authorized_link),
    ):
        """The student's own profile photo, as image bytes rather than JSON.

        Served from its own route instead of being embedded in the section
        payloads for two reasons: ``profile_photo`` is a base64 data URL that can
        run to a few hundred KB, and every section response carries the same
        ``ParentStudentRef`` -- inlining it would re-send the blob on each of the
        up-to-three consented sections, plus again in the child list. As bytes
        the browser fetches it once and reuses it from its own cache.

        ``<img src>`` cannot send an Authorization header, so the client fetches
        this through its authenticated api helper and renders an object URL.
        """
        student, _link = resolved
        raw = student.profile_photo
        if not raw or "," not in raw:
            raise HTTPException(status_code=404, detail="No photo")
        header, encoded = raw.split(",", 1)
        # Re-check the type rather than trusting the column: only the raster
        # formats a browser renders in <img> are served back.
        m = _PHOTO_MIME.match(header)
        if not m:
            raise HTTPException(status_code=404, detail="No photo")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=404, detail="No photo")
        return Response(
            content=data,
            media_type=m.group(1),
            headers={
                # The one documented exception to the no-store rule above: `private`
                # keeps this out of shared caches entirely (so one parent can never be
                # served another parent's photo), while letting the browser reuse the
                # bytes across tabs instead of refetching on every section load.
                "Cache-Control": "private, max-age=300",
                "Vary": "Authorization",
                "Content-Length": str(len(data)),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @scoped.get("/overview", response_model=OverviewResponse)
    def overview(
        response: Response,
        parent: User = Depends(get_current_parent),
        resolved: tuple = Depends(get_authorized_link),
        db: Session = Depends(get_db),
    ):
        """``basic`` scope. Identity, direction, goals, journey, passport counts.

        Unshared -> ``basic`` is ``null`` (not a 403): the page still renders and
        shows "<First name> hasn't shared this".
        """
        student, link = resolved
        response.headers.update(NO_STORE)
        parent_projection.log_read(parent.id, student.id, _served(link))
        return parent_projection.build_overview(db, student, link)

    @scoped.get("/insights", response_model=InsightsResponse)
    async def insights(
        response: Response,
        parent: User = Depends(get_current_parent),
        resolved: tuple = Depends(get_authorized_link),
        db: Session = Depends(get_db),
    ):
        """``insights`` scope. Status, focus areas and Novi's insight note.

        The only LLM call on the dashboard read path, and it is served from a
        cache keyed on the consented snapshot. Falls back to a deterministic
        template, so this endpoint cannot fail because of an AI provider.
        """
        student, link = resolved
        response.headers.update(NO_STORE)
        payload = parent_projection.build_insights_section(db, student, link)
        # Only ever ask for an insight when the section that produces it is
        # actually shared.
        if link.has_scope("insights"):
            payload.novi_insight = await parent_insight.insight_for(db, student, link)
        parent_projection.log_read(parent.id, student.id, _served(link))
        return payload

    @scoped.get("/memory", response_model=MemoryResponse)
    def memory(
        response: Response,
        resolved: tuple = Depends(get_authorized_link),
        db: Session = Depends(get_db),
    ):
        """``memory`` scope key, now "Growth history".

        No Letta: this projects ``growth_milestones`` + ``growth_snapshots`` only.
        Kept at the old path/key so stored consents keep working.
        """
        student, link = resolved
        response.headers.update(NO_STORE)
        return parent_memory.build_memory(student, link, db=db)

    return scoped


parent_scoped_router = parent_student_router()