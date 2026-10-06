# -*- coding: utf-8 -*-

import secrets
from urllib.parse import quote

from odoo import api, fields, models, _


class ZkMachineKiosk(models.Model):
    _inherit = 'zk.machine'

    active = fields.Boolean(default=True)

    device_kind = fields.Selection(
        [('physical', 'Physical biometric'), ('kiosk', 'Kiosk / tablet')],
        string='Device type',
        default='physical',
        required=True,
    )
    kiosk_token = fields.Char(
        string='Kiosk token',
        copy=False,
        readonly=True,
        index=True,
    )
    kiosk_enrollment_url = fields.Char(
        string='Kiosk enrollment URL',
        compute='_compute_kiosk_enrollment_url',
    )
    geofence_ids = fields.Many2many(
        'hr.attendance.geofence',
        'zk_machine_geofence_rel',
        'machine_id',
        'geofence_id',
        string='Geofences for this device',
    )
    default_address_id = fields.Many2one(
        'res.partner',
        string='Default working address',
        help='Used when GPS is unavailable or no geofence matches (audit only in phase 1).',
    )
    allowed_department_ids = fields.Many2many(
        'hr.department',
        'zk_machine_department_rel',
        'machine_id',
        'department_id',
        string='Allowed departments',
        help='Empty = all employees of the company may use this device.',
    )
    allowed_employee_ids = fields.Many2many(
        'hr.employee',
        'zk_machine_employee_rel',
        'machine_id',
        'employee_id',
        string='Allowed employees',
        help='Optional extra allow-list (intersection with departments).',
    )

    _sql_constraints = [
        (
            'kiosk_token_unique',
            'unique(kiosk_token)',
            'Kiosk token must be unique.',
        ),
    ]

    @api.depends('kiosk_token')
    def _compute_kiosk_enrollment_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        action = self.env.ref('hr_attendance.hr_attendance_action_kiosk_mode', raise_if_not_found=False)
        for machine in self:
            if machine.device_kind != 'kiosk' or not machine.kiosk_token or not action:
                machine.kiosk_enrollment_url = False
                continue
            token_q = quote(machine.kiosk_token, safe='')
            machine.kiosk_enrollment_url = (
                '%s/web?machine_token=%s#action=%s'
                % (base.rstrip('/'), token_q, action.id)
            )

    @api.model
    def create(self, vals):
        kind = vals.get('device_kind') or self.env.context.get('default_device_kind') or 'physical'
        vals['device_kind'] = kind
        if kind == 'kiosk':
            if not vals.get('kiosk_token'):
                vals['kiosk_token'] = self._generate_kiosk_token()
            vals.setdefault('name', _('Kiosk'))
            vals.setdefault('port_no', 0)
        return super().create(vals)

    def write(self, vals):
        if vals.get('device_kind') == 'kiosk':
            for machine in self:
                if not machine.kiosk_token and 'kiosk_token' not in vals:
                    vals = dict(vals, kiosk_token=self._generate_kiosk_token())
                    break
        return super().write(vals)

    @api.model
    def _generate_kiosk_token(self):
        return secrets.token_urlsafe(32)

    def action_regenerate_kiosk_token(self):
        for machine in self.filtered(lambda m: m.device_kind == 'kiosk'):
            machine.kiosk_token = self._generate_kiosk_token()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Kiosk token updated'),
                'message': _('Copy the new enrollment URL from the device form.'),
                'type': 'warning',
                'sticky': True,
            },
        }

    def check_connection(self):
        if self.device_kind == 'kiosk':
            return True
        return super().check_connection()

    @api.model
    def find_kiosk_by_token(self, token):
        if not token:
            return self.browse()
        token = str(token).strip()
        if '#' in token:
            token = token.split('#', 1)[0].strip()
        return self.sudo().search([
            ('device_kind', '=', 'kiosk'),
            ('kiosk_token', '=', token),
            ('active', '=', True),
        ], limit=1)

    def employee_can_punch(self, employee):
        self.ensure_one()
        employee = employee.sudo()
        if employee.company_id and self.company_id and employee.company_id != self.company_id:
            return False
        if employee.allowed_machine_ids and self not in employee.allowed_machine_ids:
            return False
        if self.allowed_employee_ids and employee not in self.allowed_employee_ids:
            return False
        if self.allowed_department_ids:
            if not employee.department_id or employee.department_id not in self.allowed_department_ids:
                if employee not in self.allowed_employee_ids:
                    return False
        return True

    def create_kiosk_punch(
        self, employee, barcode,
        latitude=None, longitude=None, geo_accuracy_m=None, geofence_match_hint=None,
    ):
        self.ensure_one()
        geo = self.env['hr.attendance.geofence'].resolve_for_machine(
            self, latitude=latitude, longitude=longitude, geo_accuracy_m=geo_accuracy_m,
        )
        if geofence_match_hint == 'denied':
            geo['geofence_match'] = 'denied'
            geo['latitude'] = False
            geo['longitude'] = False
        punch_time = fields.Datetime.now()
        punch_str = fields.Datetime.to_string(punch_time)
        device_key = 'kiosk-%s' % self.id
        vals = {
            'employee_id': employee.id,
            'device_id': device_key,
            'zk_machine_id': self.id,
            'check_in': punch_str,
            'punching_time': punch_str,
            'punch_type': 'kiosk',
            'attendance_type': 'kiosk',
            'address_id': geo.get('address_id') or self.default_address_id.id,
            'latitude': geo.get('latitude'),
            'longitude': geo.get('longitude'),
            'geo_accuracy_m': geo.get('geo_accuracy_m'),
            'geofence_id': geo.get('geofence_id'),
            'geofence_match': geo.get('geofence_match'),
        }
        return self.env['zk.machine.attendance'].sudo().with_context(
            tracking_disable=True,
        ).create(vals)

    def _kiosk_greeting_action(self, employee, next_action_xmlid):
        """Return CE-style greeting after pairing (no toggle check in/out)."""
        employee = employee.sudo()
        action_message = self.env['ir.actions.actions']._for_xml_id(
            'hr_attendance.hr_attendance_action_greeting_message'
        )
        last_att = self.env['hr.attendance'].search(
            [('employee_id', '=', employee.id)],
            order='check_in desc',
            limit=1,
        )
        previous = False
        if last_att:
            previous = last_att.check_out or last_att.check_in
        action_message['previous_attendance_change_date'] = previous
        action_message['employee_name'] = employee.name
        action_message['barcode'] = employee.barcode
        action_message['next_action'] = next_action_xmlid
        action_message['hours_today'] = employee.hours_today
        action_message['attendance'] = last_att.read()[0] if last_att else {}
        action_message['total_overtime'] = employee.total_overtime
        return {'action': action_message}
