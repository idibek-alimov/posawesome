from frappe.model.document import Document


class POSShiftReviewSettings(Document):
    def validate(self):
        from posawesome.posawesome.shift_review.policy import require_approver
        from erpnext.accounts.expense_services.shift_adjustments import validate_setup
        require_approver()
        validate_setup(self.as_dict())
