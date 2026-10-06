ITX HR Attendance Kiosk Camera
==============================

Extends Odoo 15 kiosk mode with optional camera barcode scan (BarcodeDetector API),
hide manual identification, and passes ``machine_token`` + GPS to unified punch RPC.

Requires HTTPS for camera. HID/USB scanners keep working via ``barcode_scanned`` bus.
