# -*- coding: utf-8 -*-

from odoo import fields, models

from .attendance_pairing_engine_roster import RosterAwareTimePairingEngine


class ZkMachineRoster(models.Model):
    _inherit = 'zk.machine'

    def _pair_attendance(self, employee_id, date_from, date_to, punches):
        if hasattr(self, '_zk_classify_queue'):
            punch_date = date_from.date() if hasattr(date_from, 'date') else date_from
            self._zk_classify_queue.append((employee_id, punch_date))
        engine = RosterAwareTimePairingEngine(
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            punches=punches,
            env=self.env,
        )
        return engine.pair()

    def download_attendance(self, silent=False):
        self._zk_classify_queue = []
        result = super().download_attendance(silent=silent)
        if 'attendance.classifier' in self.env:
            classifier = self.env['attendance.classifier']
            seen = set()
            for emp_id, punch_date in self._zk_classify_queue:
                key = (emp_id, punch_date)
                if key in seen:
                    continue
                seen.add(key)
                classifier.classify_employee_date(emp_id, punch_date)
        return result

    def pair_employee_work_date(self, employee_id, work_date=None, punch_dt=None):
        result = super().pair_employee_work_date(
            employee_id, work_date=work_date, punch_dt=punch_dt,
        )
        if work_date is None and punch_dt is not None:
            employee = self.env['hr.employee'].browse(employee_id)
            if isinstance(punch_dt, str):
                punch_dt = fields.Datetime.from_string(punch_dt)
            work_date = self._work_date_for_employee(employee, punch_dt)
        if 'attendance.classifier' in self.env and work_date:
            self.env['attendance.classifier'].classify_employee_date(employee_id, work_date)
        return result
