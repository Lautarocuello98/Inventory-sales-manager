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
            raise AuthorizationError("Username is required.")

        locked_until = self._locked_until.get(user_key)
        if locked_until and datetime.utcnow() < locked_until:
            remaining = int((locked_until - datetime.utcnow()).total_seconds())
            raise AuthorizationError(f"User is temporarily locked. Retry in {remaining}s.")

        user = self.repo.authenticate_user(username.strip(), pin.strip())
        if not user:
            attempts = self._failed_attempts.get(user_key, 0) + 1
            self._failed_attempts[user_key] = attempts
            if attempts >= self.policy.max_failed_attempts:
                self._locked_until[user_key] = datetime.utcnow() + timedelta(seconds=self.policy.lockout_seconds)
                self._failed_attempts[user_key] = 0
                raise AuthorizationError("Too many failed attempts. User is temporarily locked.")
            raise AuthorizationError("Invalid username or PIN.")

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
            raise AuthorizationError(f"Role '{user.role}' is not allowed to perform '{action}'.")

    def require_role(self, user: User, allowed: set[str]) -> None:
        if user.role not in allowed:
            raise AuthorizationError(f"Role '{user.role}' is not allowed to perform this action.")

    def create_user(self, actor: User, username: str, pin: str, role: str) -> int:
        self.require_action(actor, "manage_users")

        user = username.strip()
        secret = pin.strip()
        target_role = role.strip().lower()
        if not user:
            raise AuthorizationError("Username is required.")
        if len(secret) < self.policy.min_pin_length:
            raise AuthorizationError(f"PIN must have at least {self.policy.min_pin_length} characters.")
        if target_role not in {"seller", "viewer"}:
            raise AuthorizationError("Only seller or viewer users can be created.")

        try:
            return self.repo.create_user(user, secret, target_role)
        except Exception as exc:
          raise AuthorizationError(f"Could not create user '{user}': {exc}") from exc


    def change_my_pin(self, actor: User, current_pin: str, new_pin: str, confirm_pin: str) -> None:
        current_secret = current_pin.strip()
        new_secret = new_pin.strip()
        confirm_secret = confirm_pin.strip()

        if not current_secret:
            raise AuthorizationError("Current password is required.")
        if len(new_secret) < self.policy.min_pin_length:
            raise AuthorizationError(f"New password must have at least {self.policy.min_pin_length} characters.")
        if new_secret != confirm_secret:
            raise AuthorizationError("Password confirmation does not match.")
        if new_secret == current_secret:
            raise AuthorizationError("New password must be different from the current password.")

        changed = self.repo.change_user_pin(actor.id, current_secret, new_secret)
        if not changed:
            raise AuthorizationError("Current password is incorrect.")