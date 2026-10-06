# -*- coding: utf-8 -*-

from odoo import fields, models, tools


def _zk_report_daily_attendance_init(cr):
    """Build report SQL view (kiosk columns when present on punch table)."""
    tools.drop_view_if_exists(cr, 'zk_report_daily_attendance')
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zk_machine_attendance' AND column_name = 'geofence_id'
        LIMIT 1
        """
    )
    has_kiosk_geo = bool(cr.fetchone())
    if has_kiosk_geo:
        query = """
            CREATE OR REPLACE VIEW zk_report_daily_attendance AS (
                SELECT
                    MIN(z.id) AS id,
                    z.employee_id AS name,
                    z.write_date AS punching_day,
                    z.address_id AS address_id,
                    z.zk_machine_id AS zk_machine_id,
                    z.latitude AS latitude,
                    z.longitude AS longitude,
                    z.geo_accuracy_m AS geo_accuracy_m,
                    z.geofence_id AS geofence_id,
                    z.geofence_match AS geofence_match,
                    z.attendance_type AS attendance_type,
                    z.punching_time AS punching_time,
                    z.punch_type AS punch_type
                FROM zk_machine_attendance z
                    JOIN hr_employee e ON (z.employee_id = e.id)
                GROUP BY
                    z.employee_id,
                    z.write_date,
                    z.address_id,
                    z.zk_machine_id,
                    z.latitude,
                    z.longitude,
                    z.geo_accuracy_m,
                    z.geofence_id,
                    z.geofence_match,
                    z.attendance_type,
                    z.punch_type,
                    z.punching_time
            )
        """
    else:
        query = """
            CREATE OR REPLACE VIEW zk_report_daily_attendance AS (
                SELECT
                    MIN(z.id) AS id,
                    z.employee_id AS name,
                    z.write_date AS punching_day,
                    z.address_id AS address_id,
                    z.attendance_type AS attendance_type,
                    z.punching_time AS punching_time,
                    z.punch_type AS punch_type
                FROM zk_machine_attendance z
                    JOIN hr_employee e ON (z.employee_id = e.id)
                GROUP BY
                    z.employee_id,
                    z.write_date,
                    z.address_id,
                    z.attendance_type,
                    z.punch_type,
                    z.punching_time
            )
        """
    cr.execute(query)


class ZkReportDailyAttendanceKiosk(models.Model):
    _inherit = 'zk.report.daily.attendance'

    zk_machine_id = fields.Many2one('zk.machine', string='Kiosk / device', readonly=True)
    latitude = fields.Float(digits=(10, 7), readonly=True)
    longitude = fields.Float(digits=(10, 7), readonly=True)
    geo_accuracy_m = fields.Float(string='GPS accuracy (m)', readonly=True)
    geofence_id = fields.Many2one('hr.attendance.geofence', string='Geofence', readonly=True)
    geofence_match = fields.Selection(
        selection=[
            ('matched', 'Matched'),
            ('outside', 'Outside device geofences'),
            ('no_gps', 'No GPS'),
            ('no_config', 'No geofences on device'),
            ('denied', 'GPS denied'),
        ],
        readonly=True,
    )
    punch_type = fields.Selection(selection_add=[('kiosk', 'Kiosk punch')])
    attendance_type = fields.Selection(selection_add=[('kiosk', 'Kiosk')])

    def init(self):
        _zk_report_daily_attendance_init(self._cr)


from odoo.addons.hr_zk_attendance.models.machine_analysis import ReportZkDevice


def _report_init_patched(self):
    _zk_report_daily_attendance_init(self._cr)


ReportZkDevice.init = _report_init_patched
