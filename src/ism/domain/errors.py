class AppError(Exception):
    """Base app error."""


class ValidationError(AppError):
    pass


class NotFoundError(AppError):
    pass


class InsufficientStockError(AppError):
    pass


class FxUnavailableError(AppError):
    pass


class AuthorizationError(AppError):
    pass
