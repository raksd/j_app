from __future__ import annotations

LOGIN_WALL_MESSAGE = (
    "Could not read this job page (it may need a login). "
    "Paste the job title, company and description instead."
)


class JobLinkError(Exception):
    def __init__(self, message: str, needs_paste: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.needs_paste = needs_paste
