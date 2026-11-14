import unittest
from copy import deepcopy
from posawesome.posawesome.api.fiscal_contract import build_receipt, tiyin


class TestFiscalContract(unittest.TestCase):
    def invoice(self, **changes):
        doc = dict(currency="TJS", docstatus=1, taxes_and_charges="TJ Simplified Tax - R",
            items=[dict(item_code="A", qty=1, rate=10, net_amount=10)],
            grand_total=10, payments=[dict(mode_of_payment="Наличные", amount=10)])
        return dict(doc, **changes)

    def build(self, **changes):
        return build_receipt(self.invoice(**changes), {"Наличные": "Cash", "Корти Милли": "Bank"})

    def test_simplified_firmware_codes_and_integer_money(self):
        result = self.build()
        self.assertEqual((result["taxType"], result["products"][0]["vatCode"]), ("SIMPLIFIED1", "ZERO_TAX"))
        self.assertEqual(result["taxes"]["vats"][0]["vatSum"], 0)
        for key in ("receiptSum", "receiptCash", "receiptNonCash", "cashChangeAmount"):
            self.assertIs(type(result[key]), int)
        self.assertEqual(tiyin("1.005"), 101)

    def test_general_exclusive_vat_allocated_to_final_products(self):
        result = self.build(taxes_and_charges="TJ General VAT - R", grand_total=11.4,
            taxes=[dict(rate=14)], total_taxes_and_charges=1.4,
            payments=[dict(mode_of_payment="Корти Милли", amount=11.4)])
        self.assertEqual((result["taxType"], result["products"][0]["vatCode"]), ("GENERAL", "STANDARD"))
        self.assertEqual((result["receiptSum"], result["products"][0]["sum"], result["taxes"]["vats"][0]["vatSum"]), (1140, 1140, 140))

    def test_discount_and_rounding_preserve_submitted_total_exactly(self):
        result = self.build(items=[dict(item_code=str(i), qty=1, net_amount="0.33333") for i in range(3)],
            grand_total=0.99, rounded_total=1, payments=[dict(mode_of_payment="Наличные", amount=1)])
        self.assertEqual([p["sum"] for p in result["products"]], [34, 33, 33])
        self.assertEqual(result["receiptSum"], sum(p["sum"] for p in result["products"]))

    def test_return_uses_positive_tiyins_and_revert_income(self):
        result = self.build(is_return=1, grand_total=-10, items=[dict(item_code="A", qty=-2, net_amount=-10)], payments=[dict(mode_of_payment="Наличные", amount=-10)])
        self.assertEqual(result["operationType"], "REVERT_INCOME")
        self.assertEqual((result["products"][0]["quantity"], result["receiptCash"]), (2, 1000))

    def test_mixed_tender_and_cash_change(self):
        result = self.build(payments=[dict(mode_of_payment="Наличные", amount=8), dict(mode_of_payment="Корти Милли", amount=5)], change_amount=3)
        self.assertEqual(result["receiptCash"] + result["receiptNonCash"] - result["cashChangeAmount"], result["receiptSum"])

    def test_refuse_unsupported_template_rate_currency_draft_and_credit(self):
        cases = [dict(taxes_and_charges="Unknown"), dict(taxes=[dict(rate=18)]), dict(currency="USD"), dict(docstatus=0), dict(payments=[]), dict(items=[dict(qty=0, net_amount=10)])]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.build(**changes)

    def test_item_marking_and_service(self):
        result = self.build(items=[dict(item_name="Услуга", qty=1, net_amount=10, is_stock_item=0, custom_marking_code="ABC")])
        self.assertEqual((result["products"][0]["commodity"], result["products"][0]["code"]), ("SERVICE", "QUJD"))

    def test_no_mutation_of_submitted_document(self):
        doc = self.invoice(); original = deepcopy(doc)
        build_receipt(doc, {"Наличные": "Cash"})
        self.assertEqual(doc, original)

    def test_bank_tender_does_not_fabricate_acquiring_terminal_metadata(self):
        result = self.build(payments=[dict(mode_of_payment="Корти Милли", amount=10)])
        self.assertEqual(result["receiptNonCash"], 1000)
        for field in ("bankRRN", "bankCard", "bankAuthCode", "bankCardName", "bankResult"):
            self.assertIsNone(result[field])
