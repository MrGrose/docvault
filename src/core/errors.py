class ConflictError(Exception):
    pass


class IdempotencyMismatchError(Exception):
    pass


class RebaseRequiredError(Exception):
    pass


class IdempotencyRaceError(Exception):
    pass


class AuthzError(Exception):
    pass


class UngroundedError(Exception):
    pass
