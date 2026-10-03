"""Parent-safe "Growth history" -- what replaced the raw "Long-term memory" view.

Why this module exists
----------------------
The previous implementation of the ``memory`` consent section returned, verbatim
to the parent:

* every tag-matching **Letta archival passage** -- free text that the memory
  service generates from the student's conversations, and
* the **Letta core-memory ``human`` block** -- the live profile line Novi keeps
  rewriting from chat.

Both are the student's private conversation with their mentor. Tag filtering
cannot make free text safe: an LLM-written "achievement" passage is a paraphrase
of something the student said, so it carries the same content as the chat.

What it does now
----------------
The section is a projection of two tables the student owns and that contain no
conversation content:

* ``growth_milestones`` -- titles of milestones the student COMPLETED
* ``growth_snapshots``  -- a daily mean-confidence trend over ~90 days

There is **no Letta client, no HTTP call and no import of the memory stack** in
this module. That is deliberate and load-bearing: if Letta is unreachable the
response is unaffected, and there is no code path by which an archival passage
could reach a parent payload.

The internal consent key stays ``memory`` so every already-stored consent keeps
working with no migration and no change to the student's choices -- only the
display label and description changed, in both the consent UI and the parent
view.

READ-ONLY. Nothing here writes to the student's data.
"""

from app.models.user import User
from app.schemas.parent import GrowthHistory, MemoryResponse, ParentStudentRef
from app.services.parent_projection import build_growth


def build_memory(
    student: User,
    link,
    *,
    db=None,
) -> MemoryResponse:
    """Growth history for a parent, or ``growth=None`` when not shared.

    Kept under the old name/signature so the stored ``memory`` consent and the
    existing endpoint keep working unchanged.
    """
    student_ref = ParentStudentRef(
        first_name=student.first_name or "",
        grade=student.grade,
    )
    scopes = list(link.scope_names or [])

    growth: GrowthHistory | None = None
    if db is not None and link.has_scope("memory"):
        growth = build_growth(db, student)

    return MemoryResponse(
        student=student_ref,
        scopes=scopes,
        growth=growth,
    )