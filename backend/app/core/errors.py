class DomainError(Exception):
    def __init__(self, message: str, code: str = 'invalid_request', status: int = 422):
        self.message, self.code, self.status = message, code, status


def require(condition, message, code='invalid_request', status=422):
    if not condition:
        raise DomainError(message, code, status)
