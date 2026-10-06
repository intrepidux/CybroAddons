# -*- coding: utf-8 -*-

from datetime import timedelta, datetime, time

import logging
import pytz

from odoo.addons.hr_zk_attendance.models.attendance_pairing_engine import TimePairingEngine

_logger = logging.getLogger(__name__)


class RosterAwareTimePairingEngine(TimePairingEngine):
    """Pairing engine that respects WORK/OFF roster when uses_roster is set."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._off_day_dates = set()
        self._uses_roster_by_date = {}

    def _date_uses_roster(self, target_date):
        if target_date not in self._uses_roster_by_date:
            calendar = self.env['resource.calendar'].get_calendar_for_date(
                self.employee_id, target_date
            )
            self._uses_roster_by_date[target_date] = bool(
                calendar and getattr(calendar, 'uses_roster', False)
            )
        return self._uses_roster_by_date[target_date]

    def _get_work_state(self, target_date):
        return self.env['hr.roster.day'].get_work_state(self.employee_id, target_date)

    def _get_calendar_work_intervals(self):
        if not self.env or not self.employee_id:
            return super()._get_calendar_work_intervals()

        employee = self.env['hr.employee'].browse(self.employee_id)
        if not employee or not employee.exists():
            return super()._get_calendar_work_intervals()

        current_date = self.date_from.date()
        all_intervals = []
        while current_date <= self.date_to.date():
            uses_roster = self._date_uses_roster(current_date)
            work_state = self._get_work_state(current_date) if uses_roster else False

            if uses_roster and work_state == 'off':
                self._off_day_dates.add(current_date)
                current_date += timedelta(days=1)
                continue

            calendar = self.env['resource.calendar'].get_calendar_for_date(
                employee.id, current_date
            )
            if calendar and calendar.exists():
                intervals_batch = calendar._attendance_intervals_batch(
                    datetime.combine(current_date, time.min).replace(tzinfo=pytz.utc),
                    datetime.combine(
                        current_date + timedelta(days=1), time.min
                    ).replace(tzinfo=pytz.utc) - timedelta(microseconds=1),
                    resources=employee.resource_id,
                ).get(employee.resource_id.id if employee.resource_id else False, [])

                for start, stop, attendance_record in intervals_batch:
                    tolerance_before = timedelta(hours=attendance_record.tolerance_before)
                    tolerance_after = timedelta(hours=attendance_record.tolerance_after)
                    all_intervals.append({
                        'start': start,
                        'stop': stop,
                        'expanded_start': start - tolerance_before,
                        'expanded_stop': stop + tolerance_after,
                        'attendance_record_id': attendance_record.id,
                        'day_period': attendance_record.day_period,
                        'expected_hours': (stop - start).total_seconds() / 3600.0,
                        'uses_roster': uses_roster,
                        'date': current_date,
                    })
            current_date += timedelta(days=1)

        self.calendar_intervals = sorted(all_intervals, key=lambda x: x['start'])
        return self.calendar_intervals

    def _append_paired_interval(self, paired_attendances, interval, current_interval_punches):
        check_in = current_interval_punches[0]
        check_out = current_interval_punches[-1]
        lunch_duration = self.DEFAULT_LUNCH_HOURS
        punches_total_duration = (check_out - check_in).total_seconds() / 3600.0
        auto_closed = False
        auto_close_reason = False
        confidence_score = 0.0

        if len(current_interval_punches) == 1:
            paired_attendances.append({
                'check_in': check_in,
                'check_out': False,
                'has_lunch': False,
                'lunch_duration': 0.0,
                'expected_hours': interval['expected_hours'],
                'auto_closed': False,
                'auto_close_reason': False,
                'confidence_score': 0.5,
            })
            return paired_attendances

        if (
            check_out > interval['expanded_stop']
            or punches_total_duration > self.max_shift.total_seconds() / 3600.0
        ):
            auto_closed = True
            auto_close_reason = 'timeout'
            check_out = min(
                check_out,
                interval['stop'] + timedelta(hours=self.max_shift.total_seconds() / 3600.0),
            )
            confidence_score = 0.6
        else:
            confidence_score = 0.9

        paired_attendances.append({
            'check_in': check_in,
            'check_out': check_out,
            'has_lunch': True,
            'lunch_duration': lunch_duration,
            'expected_hours': interval['expected_hours'],
            'auto_closed': auto_closed,
            'auto_close_reason': auto_close_reason,
            'confidence_score': confidence_score,
        })
        return paired_attendances

    def _pair_off_day_punches(self, punches):
        if not punches:
            return []

        by_date = {}
        for punch in punches:
            punch_date = punch.astimezone(pytz.utc).date()
            uses_roster = self._date_uses_roster(punch_date)
            work_state = self._get_work_state(punch_date) if uses_roster else False
            if uses_roster and work_state == 'off':
                by_date.setdefault(punch_date, []).append(punch)

        pairs = []
        for day_punches in by_date.values():
            day_punches = sorted(day_punches)
            if len(day_punches) == 1:
                pairs.append({
                    'check_in': day_punches[0],
                    'check_out': False,
                    'has_lunch': False,
                    'lunch_duration': 0.0,
                    'expected_hours': 0.0,
                    'auto_closed': False,
                    'auto_close_reason': False,
                    'confidence_score': 0.5,
                    'roster_off_day': True,
                })
            else:
                pairs.append({
                    'check_in': day_punches[0],
                    'check_out': day_punches[-1],
                    'has_lunch': False,
                    'lunch_duration': 0.0,
                    'expected_hours': 0.0,
                    'auto_closed': False,
                    'auto_close_reason': False,
                    'confidence_score': 0.75,
                    'roster_off_day': True,
                })
        return pairs

    def _pair_sequence(self, punches):
        if not punches:
            return []

        if not self.calendar_intervals:
            self._get_calendar_work_intervals()

        paired_attendances = []
        punches_to_process = list(punches)

        for interval in self.calendar_intervals:
            current_interval_punches = sorted([
                punch for punch in punches_to_process
                if interval['expanded_start'] <= punch <= interval['expanded_stop']
            ])

            if not current_interval_punches:
                if interval.get('uses_roster'):
                    continue
                paired_attendances.append(
                    self._create_autoclosed_attendance(interval, 'window')
                )
                continue

            punches_to_process = [
                punch for punch in punches_to_process
                if punch not in current_interval_punches
            ]
            self._append_paired_interval(
                paired_attendances, interval, current_interval_punches
            )

        paired_attendances.extend(self._pair_off_day_punches(punches_to_process))
        return paired_attendances

    def pair(self):
        cleaned = self._remove_duplicates()
        return self._pair_sequence(cleaned)
