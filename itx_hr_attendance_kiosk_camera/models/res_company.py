# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_kiosk_use_camera = fields.Boolean(
        string='Kiosk camera barcode scan',
    )
    attendance_kiosk_camera_facing = fields.Selection(
        [('environment', 'Rear camera'), ('user', 'Front camera')],
        string='Kiosk camera facing',
        default='environment',
    )
    attendance_kiosk_hide_manual = fields.Boolean(
        string='Hide manual identification on kiosk',
    )
