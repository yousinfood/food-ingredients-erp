"""Shared flags to suppress sheet push / revision bump during bulk Sheet → ERP sync."""

_skip_sheet_push = False
_skip_revision_bump = False


def skip_sheet_push() -> None:
    global _skip_sheet_push
    _skip_sheet_push = True


def resume_sheet_push() -> None:
    global _skip_sheet_push
    _skip_sheet_push = False


def sheet_push_skipped() -> bool:
    return _skip_sheet_push


def skip_revision_bump() -> None:
    global _skip_revision_bump
    _skip_revision_bump = True


def resume_revision_bump() -> None:
    global _skip_revision_bump
    _skip_revision_bump = False


def revision_bump_skipped() -> bool:
    return _skip_revision_bump
