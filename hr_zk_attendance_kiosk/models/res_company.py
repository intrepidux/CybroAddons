# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_use_unified_punch = fields.Boolean(
        string='Unified punch flow (ZK + kiosk)',
        help='Kiosk scans create raw punches and run calendar pairing instead of CE toggle.',
    )
    attendance_kiosk_collect_geo = fields.Boolean(
        string='Collect GPS on kiosk punch',
        default=True,
    )
    attendance_kiosk_feedback_seconds = fields.Integer(
        string='Kiosk punch confirmation (seconds)',
        default=5,
        help='How long the success message stays on screen after a kiosk punch (3–20).',
    )
    attendance_default_kiosk_machine_id = fields.Many2one(
        'zk.machine',
        string='Default kiosk device',
        domain="[('device_kind', '=', 'kiosk'), ('company_id', 'in', [company_id, False])]",
        help='Fallback when the logged-in user has no kiosk device assigned.',
    )

    @api.constrains('attendance_kiosk_feedback_seconds')
    def _check_attendance_kiosk_feedback_seconds(self):
        for company in self:
            sec = company.attendance_kiosk_feedback_seconds
            if sec < 3 or sec > 20:
                raise ValidationError(
                    _('Kiosk punch confirmation must be between 3 and 20 seconds.')
                )
