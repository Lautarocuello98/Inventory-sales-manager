from __future__ import annotations

from ism.domain.errors import AuthorizationError
from ism.domain.models import User


class AuthService:
    def __init__(self, repo):
        self.repo = repo

    def list_users(self) -> list[User]:
        return self.repo.list_users()

    def login(self, username: str, pin: str) -> User:
        user = self.repo.authenticate_user(username.strip(), pin.strip())
        if not user:
            raise AuthorizationError("Usuario o PIN inválido.")
        return user

    def require_role(self, user: User, allowed: set[str]) -> None:
        if user.role not in allowed:
            raise AuthorizationError(f"El rol '{user.role}' no tiene permisos para esta acción.")