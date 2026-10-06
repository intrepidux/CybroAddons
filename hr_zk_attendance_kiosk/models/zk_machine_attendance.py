# -*- coding: utf-8 -*-

from odoo import fields, models


class ZkMachineAttendanceKiosk(models.Model):
    _inherit = 'zk.machine.attendance'

    zk_machine_id = fields.Many2one('zk.machine', string='Kiosk / device', index=True, ondelete='set null')
    punch_type = fields.Selection(selection_add=[('kiosk', 'Kiosk punch')])
    attendance_type = fields.Selection(selection_add=[('kiosk', 'Kiosk')])
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    geo_accuracy_m = fields.Float(string='GPS accuracy (m)')
    geofence_id = fields.Many2one('hr.attendance.geofence', string='Geofence', ondelete='set null')
    geofence_match = fields.Selection([
        ('matched', 'Matched'),
        ('outside', 'Outside device geofences'),
        ('no_gps', 'No GPS'),
        ('no_config', 'No geofences on device'),
        ('denied', 'GPS denied'),
    ], string='Geofence match')
