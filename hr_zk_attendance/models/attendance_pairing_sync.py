# -*- coding: utf-8 -*-

from datetime import datetime as dt_datetime, time as dt_time, timedelta

import logging
import pytz

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ZkMachinePairingSync(models.Model):
    _inherit = 'zk.machine'

    def _employee_timezone(self, employee):
        return pytz.timezone(employee.tz or self.env.user.tz or 'UTC')

    def _work_date_for_employee(self, employee, punch_dt):
        """Return the calendar work date in the employee timezone."""
        tz = self._employee_timezone(employee)
        if punch_dt.tzinfo is None:
            punch_dt = pytz.utc.localize(punch_dt)
        else:
            punch_dt = punch_dt.astimezone(pytz.utc)
        return punch_dt.astimezone(tz).date()

    def _work_day_utc_bounds(self, employee, work_date):
        """UTC naive bounds covering the employee's local work_date."""
        tz = self._employee_timezone(employee)
        start_local = tz.localize(dt_datetime.combine(work_date, dt_time.min))
        end_local = tz.localize(dt_datetime.combine(work_date, dt_time.max))
        start_utc = start_local.astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = end_local.astimezone(pytz.utc).replace(tzinfo=None)
        return start_utc, end_utc

    def _collect_punches_for_employee_day(self, employee_id, work_date):
        """All raw punch datetimes (UTC naive) for employee on work_date (employee TZ)."""
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee.exists():
            return []
        start_utc, end_utc = self._work_day_utc_bounds(employee, work_date)
        punches = self.env['zk.machine.attendance'].search([
            ('employee_id', '=', employee_id),
            ('punching_time', '>=', fields.Datetime.to_string(start_utc)),
            ('punching_time', '<=', fields.Datetime.to_string(end_utc)),
        ], order='punching_time asc')
        result = []
        for punch in punches:
            if not punch.punching_time:
                continue
            dt = fields.Datetime.from_string(punch.punching_time)
            result.append(dt)
        return result

    def _apply_pairing_to_hr(self, employee_id, work_date, punches_datetimes=None):
        """Run TimePairingEngine and upsert hr.attendance for one employee-day."""
        if punches_datetimes is None:
            punches_datetimes = self._collect_punches_for_employee_day(employee_id, work_date)

        start_date = dt_datetime.combine(work_date, dt_time.min)
        end_date = dt_datetime.combine(work_date, dt_time.max)

        paired_records = self._pair_attendance(
            employee_id=employee_id,
            date_from=start_date,
            date_to=end_date,
            punches=punches_datetimes,
        )

        att_obj = self.env['hr.attendance']
        created_hr = 0
        updated_hr = 0

        for pair in paired_records:
            check_in_dt = pair.get('check_in')
            check_out_dt = pair.get('check_out')
            if not check_in_dt:
                continue

            check_in_str = fields.Datetime.to_string(check_in_dt)
            check_out_str = fields.Datetime.to_string(check_out_dt) if check_out_dt else False

            lunch_duration = pair.get('lunch_duration', 1.0)
            expected_hours = pair.get('expected_hours', 0.0)
            auto_closed = pair.get('auto_closed', False)
            auto_close_reason = pair.get('auto_close_reason', False)
            confidence_score = pair.get('confidence_score', 0.0)

            existing = att_obj.search([
                ('employee_id', '=', employee_id),
                ('check_in', '=', check_in_str),
            ], limit=1)

            vals = {
                'check_out': check_out_str,
                'lunch_duration_deducted': lunch_duration,
                'expected_hours': expected_hours,
                'auto_closed': auto_closed,
                'auto_close_reason': auto_close_reason,
                'confidence_score': confidence_score,
            }

            if existing:
                if check_out_str or any(k in pair for k in ('auto_closed', 'expected_hours')):
                    try:
                        existing.write(vals)
                        updated_hr += 1
                    except Exception as e:
                        _logger.error('Error updating attendance %s: %s', existing.id, e)
            else:
                if check_out_str or not auto_closed:
                    try:
                        att_obj.create({
                            'employee_id': employee_id,
                            'check_in': check_in_str,
                            **vals,
                        })
                        created_hr += 1
                    except Exception as e:
                        _logger.error('Error creating HR attendance: %s', e)

        return {'created': created_hr, 'updated': updated_hr, 'pairs': len(paired_records)}

    def pair_employee_work_date(self, employee_id, work_date=None, punch_dt=None):
        """Re-pair a single employee-day after a new punch (kiosk or ZK)."""
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee.exists():
            return {'created': 0, 'updated': 0, 'pairs': 0}
        if work_date is None:
            if punch_dt is None:
                punch_dt = fields.Datetime.now()
            if isinstance(punch_dt, str):
                punch_dt = fields.Datetime.from_string(punch_dt)
            work_date = self._work_date_for_employee(employee, punch_dt)
        return self._apply_pairing_to_hr(employee_id, work_date)

    @api.model
    def cron_download(self):
        Machine = self.env['zk.machine']
        if 'device_kind' in Machine._fields:
            machines = Machine.search([('device_kind', '=', 'physical')])
        else:
            machines = Machine.search([])
        for machine in machines:
            machine.download_attendance(silent=True)
