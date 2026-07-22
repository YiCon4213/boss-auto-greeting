from agent_app.domain.schemas import ProfileRead, ProfileUpdate
from agent_app.infrastructure.repositories import ProfileRepository


class ProfileService:
    sensitive_fields = frozenset({"email", "phone", "address"})

    def __init__(self, repository: ProfileRepository | None = None):
        self.repository = repository

    @staticmethod
    def model_context(profile: ProfileUpdate) -> dict[str, object]:
        context: dict[str, object] = {}
        visibility = profile.field_visibility
        for field_name in type(profile).model_fields:
            if field_name == "field_visibility":
                continue
            value = getattr(profile, field_name)
            if value is None or value == "" or value == [] or value == {}:
                continue
            default_visible = field_name not in ProfileService.sensitive_fields
            if not visibility.get(field_name, default_visible):
                continue
            context[field_name] = value
        return context

    def get_current(self) -> ProfileRead | None:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")
        record = self.repository.get_current()
        if record is None:
            return None
        return ProfileRead(id=record.id, version=record.version, **record.payload)

    def save(self, profile: ProfileUpdate) -> ProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")
        record = self.repository.save(profile.model_dump(mode="json"))
        return ProfileRead(id=record.id, version=record.version, **record.payload)
