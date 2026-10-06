# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrEmployeeKiosk(models.Model):
    _inherit = 'hr.employee'

    allowed_machine_ids = fields.Many2many(
        'zk.machine',
        'hr_employee_zk_machine_rel',
        'employee_id',
        'machine_id',
        string='Allowed kiosk/biometric devices',
        help='If set, employee may only punch on these devices (in addition to device ACL).',
    )

    def _resolve_kiosk_machine(self, machine_token=None, machine_id=None):
        """Resolve kiosk device: explicit id/token, then user/company assignment."""
        Machine = self.env['zk.machine'].sudo()
        machine = Machine.browse()
        if machine_token:
            machine = Machine.find_kiosk_by_token(machine_token)
        if not machine and machine_id:
            candidate = Machine.browse(machine_id)
            if (
                candidate.exists()
                and candidate.device_kind == 'kiosk'
                and candidate.active
            ):
                machine = candidate
        if not machine:
            session = self.env.user.get_attendance_kiosk_session()
            if session.get('machine_id'):
                candidate = Machine.browse(session['machine_id'])
                if (
                    candidate.exists()
                    and candidate.device_kind == 'kiosk'
                    and candidate.active
                ):
                    machine = candidate
            elif session.get('machine_token'):
                machine = Machine.find_kiosk_by_token(session['machine_token'])
        return machine

    @api.model
    def attendance_scan(
        self,
        barcode,
        machine_token=None,
        machine_id=None,
        latitude=None,
        longitude=None,
        geo_accuracy_m=None,
        geofence_match_hint=None,
    ):
        company = self.env.company
        if not company.attendance_use_unified_punch:
            return super().attendance_scan(barcode)

        machine = self._resolve_kiosk_machine(
            machine_token=machine_token,
            machine_id=machine_id,
        )
        if not machine:
            return {
                'warning': _(
                    'No kiosk device configured. Assign a kiosk device on your user '
                    '(or company default), or open the enrollment URL from the device form.'
                ),
            }

        employee = self.sudo().search([('barcode', '=', barcode)], limit=1)
        if not employee:
            return {
                'warning': _("No employee corresponding to Badge ID '%s'.") % barcode,
            }

        if not machine.employee_can_punch(employee):
            return {
                'warning': _('You are not allowed to register attendance on this device.'),
            }

        if geofence_match_hint == 'denied':
            latitude = longitude = geo_accuracy_m = None

        machine.sudo().create_kiosk_punch(
            employee,
            barcode,
            latitude=latitude,
            longitude=longitude,
            geo_accuracy_m=geo_accuracy_m,
            geofence_match_hint=geofence_match_hint,
        )
        machine.sudo().pair_employee_work_date(employee.id)

        return {
            'success': True,
            'employee_name': employee.name,
            'machine_id': machine.id,
            'machine_name': machine.name,
            'message': _(
                'Punch recorded on %s. Attendance is calculated from your work schedule.'
            ) % machine.name,
        }
