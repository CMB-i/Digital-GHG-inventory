"""
Canonical submission/package status vocabulary, shared by SUBMIT and APPROV.

PERIOD and VALSET have their own, separate status lifecycles -- this module
is only for the Draft -> Submitted/Resubmitted -> Under Review ->
Approved/Rejected/Changes Requested lifecycle shared by Submission and
SubmissionPackage.
"""

STATUS_DRAFT = "Draft"
STATUS_SUBMITTED = "Submitted"
STATUS_RESUBMITTED = "Resubmitted"
STATUS_UNDER_REVIEW = "Under Review"
STATUS_CHANGES_REQUESTED = "Changes Requested"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"

# Directly editable by the submitter.
EDITABLE_SUBMISSION_STATUSES = (STATUS_DRAFT, STATUS_CHANGES_REQUESTED)

# Awaiting or undergoing reviewer action.
REVIEWABLE_STATUSES = (STATUS_SUBMITTED, STATUS_RESUBMITTED, STATUS_UNDER_REVIEW)

# Human-readable label per status, shared by SUBMIT/APPROV history and audit views.
SUBMISSION_STATUS_LABELS = {
    STATUS_APPROVED: "Approved and locked",
    STATUS_DRAFT: "Draft saved",
    STATUS_CHANGES_REQUESTED: "Needs correction",
    STATUS_REJECTED: "Sent back",
    STATUS_RESUBMITTED: "Sent again for review",
    STATUS_UNDER_REVIEW: "Under review",
    STATUS_SUBMITTED: "Submitted",
}
