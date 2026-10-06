# -*- coding: utf-8 -*-
###################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2018-TODAY Cybrosys Technologies(<http://www.cybrosys.com>).
#    Author: cybrosys(<https://www.cybrosys.com>).
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###################################################################################
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.tools import float_utils
from odoo.exceptions import ValidationError
from odoo.addons.resource.models.resource import Intervals

import logging

_logger = logging.getLogger(__name__)


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    day_period = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('cross_day', 'Cross Day / Noche')
    ], required=True, default='morning', string="Periodo del Día")

    tolerance_before = fields.Float(
        default=1.0,
        string="Tolerancia Antes (horas)",
        help="Horas de tolerancia antes del inicio del turno para aceptar un Check-in válido"
    )

    tolerance_after = fields.Float(
        default=2.0,
        string="Tolerancia Después (horas)",
        help="Horas de tolerancia después del fin del turno para aceptar un Check-out válido"
    )

    @api.onchange('hour_from', 'hour_to', 'day_period')
    def _onchange_hours(self):
        """
        Sobreescribir método original para permitir hour_to < hour_from
        cuando el periodo es Cross Day (Noche)
        """
        # avoid negative or after midnight
        self.hour_from = min(self.hour_from, 23.99)
        self.hour_from = max(self.hour_from, 0.0)
        self.hour_to = min(self.hour_to, 24)
        self.hour_to = max(self.hour_to, 0.0)

        # Para cross_day NO aplicar la validación de orden
        if self.day_period != 'cross_day':
            self.hour_to = max(self.hour_to, self.hour_from)

    @api.constrains('hour_from', 'hour_to', 'day_period')
    def _check_hours(self):
        """
        Validación adicional para Cross Day
        """
        for record in self:
            if record.day_period != 'cross_day' and float_utils.float_compare(record.hour_to, record.hour_from, 2) < 0:
                raise ValidationError(_("La hora de fin debe ser mayor que la hora de inicio"))


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    def _compute_hours_per_day(self, attendances):
        if not attendances:
            return 0

        hour_count = 0.0
        # Calculate total hours accounting for cross-day shifts
        for attendance in attendances:
            if attendance.day_period == 'cross_day' and attendance.hour_to < attendance.hour_from:
                hour_count += (24 - attendance.hour_from) + attendance.hour_to
            else:
                hour_count += attendance.hour_to - attendance.hour_from

        # Determine the number of unique days of the week covered by all attendances.
        # This handles both normal and cross_day shifts properly counting the affected days.
        days_covered_by_attendances = set()
        for attendance in attendances:
            dayofweek = int(attendance.dayofweek)
            days_covered_by_attendances.add(dayofweek)
            if attendance.day_period == 'cross_day' and attendance.hour_to < attendance.hour_from:
                days_covered_by_attendances.add((dayofweek + 1) % 7)
        
        if not days_covered_by_attendances:
            return 0

        number_of_days = len(days_covered_by_attendances)

        return float_utils.float_round(hour_count / float(number_of_days), precision_digits=2)




    def _check_overlap(self, attendance_ids):
        """
        Extender el método _check_overlap para manejar turnos nocturnos (cross_day)
        """
        result = []
        for attendance in attendance_ids.filtered(lambda att: not att.date_from and not att.date_to):
            # 0.000001 is added to each start hour to avoid to detect two contiguous intervals as superimposing.
            # Indeed Intervals function will join 2 intervals with the start and stop hour corresponding.
            if attendance.day_period == 'cross_day':
                # Turno que cruza medianoche: dividir en dos intervalos
                result.append((int(attendance.dayofweek) * 24 + attendance.hour_from + 0.000001, int(attendance.dayofweek) * 24 + 24, attendance))
                # Asegurarse de que el día siguiente no exceda '6' (domingo)
                next_dayofweek = (int(attendance.dayofweek) + 1) % 7
                result.append((next_dayofweek * 24 + 0.000001, next_dayofweek * 24 + attendance.hour_to, attendance))
            else:
                # Turno normal del mismo día
                result.append((int(attendance.dayofweek) * 24 + attendance.hour_from + 0.000001, int(attendance.dayofweek) * 24 + attendance.hour_to, attendance))

        if len(Intervals(result)) != len(result):
            raise ValidationError(_("No se pueden superponer las asistencias."))

    def _attendance_intervals_batch(self, start_dt, end_dt, resources=None, domain=None, tz=None):
        """
        Extender método para fusionar intervalos Cross Day consecutivos
        en una sola ventana lógica para el motor de pairing
        """
        # Ejecutar método original
        res = super(ResourceCalendar, self)._attendance_intervals_batch(
            start_dt, end_dt, resources=resources, domain=domain, tz=tz
        )

        # Procesar fusion de intervalos Cross Day
        for resource_id, intervals in res.items():
            fused = []
            skip_next = False

            for i, interval in enumerate(intervals):
                if skip_next:
                    skip_next = False
                    continue

                start, stop, attendance = interval

                # Verificar si es Cross Day y hay un intervalo siguiente
                if attendance.day_period == 'cross_day' and i < len(intervals) - 1:
                    next_start, next_stop, next_attendance = intervals[i+1]

                    # Fusionar si el siguiente intervalo también es Cross Day y es consecutivo
                    if next_attendance.day_period == 'cross_day' and abs(start.day - next_start.day) <= 1:
                        _logger.info("Fusionando intervalos Cross Day: %s -> %s y %s -> %s",
                                     start, stop, next_start, next_stop)

                        fused.append((
                            start,
                            next_stop,
                            attendance
                        ))
                        skip_next = True
                        continue

                fused.append(interval)

            # Reemplazar con los intervalos fusionados
            res[resource_id]._items = fused

        return res

    # ------------------------------------------------------------------
    #  Custom compute methods for hr_payroll fields
    # ------------------------------------------------------------------
    @api.depends('attendance_ids.hour_from', 'attendance_ids.hour_to', 'attendance_ids.day_period', 'attendance_ids.work_entry_type_id.is_leave')
    def _compute_hours_per_week(self):
        """Override to correctly handle cross_day shifts.
        The original method in hr_payroll simply subtracted hour_to - hour_from
        which produced negative values for cross_day.  This implementation
        mirrors the logic used in the attendance calculation above.
        """
        for calendar in self:
            sum_hours = 0.0
            for att in calendar.attendance_ids:
                if att.work_entry_type_id and att.work_entry_type_id.is_leave:
                    continue
                if att.day_period == 'cross_day' and att.hour_to < att.hour_from:
                    sum_hours += (24 - att.hour_from) + att.hour_to
                else:
                    sum_hours += att.hour_to - att.hour_from
            calendar.hours_per_week = sum_hours / 2 if calendar.two_weeks_calendar else sum_hours

    @api.depends('hours_per_week', 'full_time_required_hours')
    def _compute_work_time_rate(self):
        """Override to ensure a positive rate between 0 and 100.
        Handles division by zero when full_time_required_hours is 0.
        """
        for calendar in self:
            if not calendar.hours_per_week:
                calendar.work_time_rate = 0.0
                continue
            if calendar.full_time_required_hours:
                rate = calendar.hours_per_week / calendar.full_time_required_hours * 100
            else:
                rate = 100.0
            calendar.work_time_rate = max(0.0, min(rate, 100.0))
