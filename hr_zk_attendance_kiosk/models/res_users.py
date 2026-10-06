# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    attendance_kiosk_machine_id = fields.Many2one(
        'zk.machine',
        string='Kiosk device',
        domain="[('device_kind', '=', 'kiosk'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Used when opening Kiosk Mode from the Attendance menu (no enrollment URL).',
    )

    def get_attendance_kiosk_session(self):
        """Return kiosk machine token for the current operator session."""
        self.ensure_one()
        machine = self.sudo().attendance_kiosk_machine_id
        if not machine:
            machine = self.env.company.sudo().attendance_default_kiosk_machine_id
        if not machine or machine.device_kind != 'kiosk' or not machine.active:
            return {}
        return {
            'machine_token': machine.kiosk_token,
            'machine_id': machine.id,
            'machine_name': machine.name,
        }

    @api.model
    def get_attendance_kiosk_session_public(self):
        return self.env.user.sudo().get_attendance_kiosk_session()
