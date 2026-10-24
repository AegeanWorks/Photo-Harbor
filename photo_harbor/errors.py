"""The one error type photo-harbor raises for problems a person can fix."""


class HarborError(Exception):
    """A failure with a cause and a remedy, mapped to an HTTP status when served."""

    def __init__(self, message: str, why: str, fix: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.why = why
        self.fix = fix
        self.status = status

    def as_text(self) -> str:
        return f"Error: {self.message}\nWhy: {self.why}\nFix: {self.fix}"

    def as_dict(self) -> dict:
        return {"error": self.message, "why": self.why, "fix": self.fix}
