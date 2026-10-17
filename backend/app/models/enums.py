import enum


class UserRole(str, enum.Enum):
    STUDENT = "student"
    PARENT = "parent"


class LinkStatus(str, enum.Enum):
    """Lifecycle of a parent -> student link.

    Legacy requests start PENDING and require student approval. A parent-created
    student starts with an ACTIVE link and explicit activation provenance.
    """

    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class PassportCategory(str, enum.Enum):
    PROJECTS = "projects"
    COMPETITIONS = "competitions"
    CERTIFICATIONS = "certifications"
    LEADERSHIP = "leadership"
    RESEARCH = "research"
    ACTIVITIES = "activities"
    ACHIEVEMENTS = "achievements"


class GoalCategory(str, enum.Enum):
    CAREER = "career"
    UNIVERSITY = "university"
    ACADEMIC = "academic"
    EXTRACURRICULAR = "extracurricular"
    PERSONAL = "personal"


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


class PrioritySkill(str, enum.Enum):
    BUILD = "build"
    EXPLORE = "explore"
    GROW = "grow"


class RoadmapStage(str, enum.Enum):
    DISCOVER = "discover"
    EXPLORE = "explore"
    BUILD = "build"
    APPLY = "apply"
    FOUNDATIONS = "foundations"


class CheckinStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    SUMMARIZED = "summarized"


DailyCheckinStatus = CheckinStatus


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
