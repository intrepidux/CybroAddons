# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    expected_hours = fields.Float(
        string="Horas Teóricas",
        help="Horas esperadas según el calendario del empleado."
    )
    auto_closed = fields.Boolean(
        string="Cerrado Automáticamente",
        default=False,
        help="Indica si la asistencia fue cerrada automáticamente por el sistema."
    )
    auto_close_reason = fields.Selection([
        ('next_punch', 'Cerrado por siguiente marca'),
        ('window', 'Cerrado por fin de ventana de trabajo'),
        ('timeout', 'Cerrado por timeout (exceso de horas)')
    ],
        string="Razón de Cierre Automático",
        help="Describe la razón por la cual la asistencia fue cerrada automáticamente."
    )
    confidence_score = fields.Float(
        string="Nivel de Confianza (Pairing)",
        help="Puntuación que indica la confianza del emparejamiento de marcas. (Opcional)"
    )
