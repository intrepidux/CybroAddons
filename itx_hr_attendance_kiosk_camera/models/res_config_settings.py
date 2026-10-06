# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_kiosk_use_camera = fields.Boolean(
        related='company_id.attendance_kiosk_use_camera',
        readonly=False,
    )
    attendance_kiosk_camera_facing = fields.Selection(
        related='company_id.attendance_kiosk_camera_facing',
        readonly=False,
    )
    attendance_kiosk_hide_manual = fields.Boolean(
        related='company_id.attendance_kiosk_hide_manual',
        readonly=False,
    )
