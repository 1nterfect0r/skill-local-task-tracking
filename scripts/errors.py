class TaskTrackingError(Exception):
    code = "UNEXPECTED_ERROR"
    exit_code = 10

    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(TaskTrackingError):
    code = "VALIDATION_ERROR"
    exit_code = 2


class NotFoundError(TaskTrackingError):
    code = "NOT_FOUND"
    exit_code = 3


class ConflictError(TaskTrackingError):
    code = "CONFLICT"
    exit_code = 4


class IntegrityError(TaskTrackingError):
    code = "INTEGRITY_ERROR"
    exit_code = 5
