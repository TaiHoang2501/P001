from dataclasses import dataclass

from src.db.models import ActorType, Channel, User, UserRole


@dataclass(frozen=True)
class Actor:
    """Who is performing a service call.

    The user always comes from the authenticated session (JWT), never from LLM arguments.
    `via` records whether the action came from the web UI or the AI agent (audit trail).
    """

    user: User
    via: Channel = Channel.WEB

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def role(self) -> UserRole:
        return self.user.role

    @property
    def actor_type(self) -> ActorType:
        return ActorType.AI_AGENT if self.via == Channel.AI_AGENT else ActorType.USER
