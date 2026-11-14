# Printed-sample receipt previews

These are synthetic **ordinary store receipts**, generated from the current shared
`renderMarketReceipt` renderer and rendered by headless Chrome on 2026-11-14.
They do not record sales, open shifts, contact a printer or register fiscal documents.
Names, tax IDs and document numbers are deliberately fictional.

| Scenario | HTML | Image | 80 mm PDF |
| --- | --- | --- | --- |
| Cash sale | [sale.html](sale.html) | [sale.png](sale.png) | [sale.pdf](sale.pdf) |
| Discount, exclusive VAT, split cash/bank and loyalty balance | [discounted.html](discounted.html) | [discounted.png](discounted.png) | [discounted.pdf](discounted.pdf) |
| Return to customer credit | [return.html](return.html) | [return.png](return.png) | [return.pdf](return.pdf) |

All three have Tajik labels, comma monetary decimals, three-decimal quantities,
monospaced text, dashed sections and a Code128 invoice barcode. The discounted
example is `240 − 50 + 26.60 = 216.60`; payment is `120 + 100 − 3.40 = 216.60`.
The return example refunds 177 to customer credit and pays out zero cash.

Chrome confirmed no overflowing item/math/metadata rows in these fixtures. The
real Electron 33.4.11 runtime also loaded/measured the discounted HTML through
the native printing helper with its spooler call stubbed. This does not establish
physical font support, barcode scanning, cutter operation, OS driver installation,
QZ output or the TP809 firmware's official fiscal layout/QR.

For fiscal receipts the application sends validated integer-tiyin JSON to the
TP809; that firmware generates the official identifiers and QR itself. Ordinary
printing never calls `/api/formReceipt`.
