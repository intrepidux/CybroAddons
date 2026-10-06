HR ZK Attendance Kiosk
======================

Unified punch flow: kiosk scans write to ``zk.machine.attendance`` and run the same
``TimePairingEngine`` as ZK downloads.

Install
-------

1. Install ``hr_zk_attendance`` and this module.
2. Settings → Attendances → enable **Unified punch flow**.
3. Create a **Kiosk / tablet** device; copy the enrollment URL (auto-generated token).
4. Configure **Geofences** and link them on each kiosk device.
5. Optional: ``itx_hr_attendance_kiosk_camera`` for camera + hide manual UI.

TEST server (glowicom.intrepidux.com)
-------------------------------------

Verify ``hr_employee_calendar_history`` is installed (``get_calendar_for_date``).
Optional: ``hr_zk_attendance_roster`` if ``hr_roster`` is used.
