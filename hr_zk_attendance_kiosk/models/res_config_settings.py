# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_use_unified_punch = fields.Boolean(
        related='company_id.attendance_use_unified_punch',
        readonly=False,
    )
    attendance_kiosk_collect_geo = fields.Boolean(
        related='company_id.attendance_kiosk_collect_geo',
        readonly=False,
    )
    attendance_kiosk_feedback_seconds = fields.Integer(
        related='company_id.attendance_kiosk_feedback_seconds',
        readonly=False,
    )
    attendance_default_kiosk_machine_id = fields.Many2one(
        related='company_id.attendance_default_kiosk_machine_id',
        readonly=False,
    )
