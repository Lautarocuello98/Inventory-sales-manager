from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ism.domain.errors import AuthorizationError
from ism.domain.models import User


@dataclass(frozen=True)
class LoginPolicy:
    min_pin_length: int = 4
    max_failed_attempts: int = 5
    lockout_seconds: int = 60


PERMISSIONS: dict[str, set[str]] = {
    "create_product": {"admin"},
    "delete_product": {"admin"},
    "create_sale": {"admin", "seller"},
    "create_restock": {"admin", "seller"},
    "import_excel": {"admin", "seller"},
    "export_report": {"admin", "seller", "viewer"},
    "manage_users": {"admin"},
}


class AuthService:
    def __init__(self, repo, policy: LoginPolicy | None = None):
        self.repo = repo
        self.policy = policy or LoginPolicy()
        self._failed_attempts: dict[str, int] = {}
        self._locked_until: dict[str, datetime] = {}

    def list_users(self) -> list[User]:
        return self.repo.list_users()

    def login(self, username: str, pin: str) -> User:
        user_key = username.strip().lower()
        if not user_key:
            raise AuthorizationError("El usuario es obligatorio.")

        locked_until = self._locked_until.get(user_key)
        if locked_until and datetime.utcnow() < locked_until:
            remaining = int((locked_until - datetime.utcnow()).total_seconds())
            raise AuthorizationError(f"Usuario temporalmente bloqueado. Reintentar en {remaining}s.")

        user = self.repo.authenticate_user(username.strip(), pin.strip())
        if not user:
            attempts = self._failed_attempts.get(user_key, 0) + 1
            self._failed_attempts[user_key] = attempts
            if attempts >= self.policy.max_failed_attempts:
                self._locked_until[user_key] = datetime.utcnow() + timedelta(seconds=self.policy.lockout_seconds)
                self._failed_attempts[user_key] = 0
                raise AuthorizationError("Demasiados intentos fallidos. Usuario bloqueado temporalmente.")
            raise AuthorizationError("Usuario o PIN inválido.")

        self._failed_attempts.pop(user_key, None)
        self._locked_until.pop(user_key, None)
        return user

    def can(self, user: User, action: str) -> bool:
        allowed_roles = PERMISSIONS.get(action)
        if not allowed_roles:
            return False
        return user.role in allowed_roles

    def require_action(self, user: User, action: str) -> None:
        if not self.can(user, action):
            raise AuthorizationError(f"El rol '{user.role}' no tiene permisos para '{action}'.")

    def require_role(self, user: User, allowed: set[str]) -> None:
        if user.role not in allowed:
            raise AuthorizationError(f"El rol '{user.role}' no tiene permisos para esta acción.")

    def create_user(self, actor: User, username: str, pin: str, role: str) -> int:
        self.require_action(actor, "manage_users")

        user = username.strip()
        secret = pin.strip()
        target_role = role.strip().lower()
        if not user:
            raise AuthorizationError("El usuario es obligatorio.")
        if len(secret) < self.policy.min_pin_length:
            raise AuthorizationError(f"El PIN debe tener al menos {self.policy.min_pin_length} caracteres.")
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
        if len(new_secret) < self.policy.min_pin_length:
            raise AuthorizationError(f"La nueva contraseña debe tener al menos {self.policy.min_pin_length} caracteres.")
        if new_secret != confirm_secret:
            raise AuthorizationError("La confirmación de la contraseña no coincide.")
        if new_secret == current_secret:
            raise AuthorizationError("La nueva contraseña debe ser distinta a la actual.")

        changed = self.repo.change_user_pin(actor.id, current_secret, new_secret)
        if not changed:
            raise AuthorizationError("La contraseña actual es incorrecta.")
