"""Domain exceptions of the trip planner service."""


class InvalidRequestError(Exception):
    """The request cannot be answered as given (reported as HTTP 400)."""


class TransientActionError(Exception):
    """An environment action failed in a way that a retry may fix."""
