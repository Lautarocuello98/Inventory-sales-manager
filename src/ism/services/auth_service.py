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

    def create_user(self, actor: User, username: str, pin: str, role: str) -> int:
        self.require_role(actor, {"admin"})

        user = username.strip()
        secret = pin.strip()
        target_role = role.strip().lower()
        if not user:
            raise AuthorizationError("El usuario es obligatorio.")
        if len(secret) < 4:
            raise AuthorizationError("El PIN debe tener al menos 4 caracteres.")
        if target_role not in {"seller", "viewer"}:
            raise AuthorizationError("Solo se pueden crear usuarios con rol seller o viewer.")

        try:
            return self.repo.create_user(user, secret, target_role)
        except Exception as exc:
            raise AuthorizationError(f"No se pudo crear el usuario '{user}': {exc}") from exc


    def change_my_pin(self, actor: User, current_pin: str, new_pin: str, confirm_pin: str) -> None:
        current_secret = current_pin.strip()
        new_secret = new_pin.strip()
        confirm_secret = confirm_pin.strip()

        if not current_secret:
            raise AuthorizationError("La contraseña actual es obligatoria.")
        if len(new_secret) < 4:
            raise AuthorizationError("La nueva contraseña debe tener al menos 4 caracteres.")
        if new_secret != confirm_secret:
            raise AuthorizationError("La confirmación de la contraseña no coincide.")
        if new_secret == current_secret:
            raise AuthorizationError("La nueva contraseña debe ser distinta a la actual.")

        changed = self.repo.change_user_pin(actor.id, current_secret, new_secret)
        if not changed:
            raise AuthorizationError("La contraseña actual es incorrecta.")