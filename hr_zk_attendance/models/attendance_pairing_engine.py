# -*- coding: utf-8 -*-

from datetime import timedelta, datetime, time
from odoo import api, fields, models, _
import pytz
import logging

_logger = logging.getLogger(__name__)


class TimePairingEngine:

    def __init__(
        self,
        employee_id, 
        date_from, 
        date_to,
        punches, # Ahora son todos los punches para el rango de fechas
        duplicate_threshold_minutes=3, # Aumentado a 3 min por ser más común
        min_pair_minutes=3,
        max_shift_hours=16,
        lunch_threshold_hours=3,
        env=None # Pasar el env para poder usar la API de Odoo
    ):
        self.env = env # Se requiere el entorno de Odoo para consultar modelos
        self.employee_id = employee_id
        self.date_from = date_from
        self.date_to = date_to
        # Convertir todas las marcas a datetime con zona horaria UTC
        # Esto evita comparaciones entre datetime naive y aware.
        aware_punches = []
        for p in punches:
            if p.tzinfo is None:
                # Asumimos que los punches provienen del dispositivo en UTC
                aware_punches.append(p.replace(tzinfo=pytz.utc))
            else:
                aware_punches.append(p.astimezone(pytz.utc))
        self.punches = sorted(aware_punches)  # punches debe ser una lista de datetimes
        self.duplicate_threshold = timedelta(minutes=duplicate_threshold_minutes)
        self.min_pair = timedelta(minutes=min_pair_minutes)
        self.max_shift = timedelta(hours=max_shift_hours)
        self.lunch_threshold = timedelta(hours=lunch_threshold_hours)
        
        # Nuevos atributos para el calendario
        self.calendar_intervals = [] # Se llenará con los intervalos de trabajo del calendario

    # -------------------------------------------------------
    # STEP 1 — remove duplicate punches
    # -------------------------------------------------------

    def _remove_duplicates(self):

        cleaned = []

        for punch in self.punches:

            if not cleaned:
                cleaned.append(punch)
                continue

            diff = punch - cleaned[-1]

            if diff > self.duplicate_threshold:
                cleaned.append(punch)

        return cleaned

    # -------------------------------------------------------
    # STEP 2 — Obtener intervalos de trabajo del calendario
    # -------------------------------------------------------
    def _get_calendar_work_intervals(self):
        if not self.env or not self.employee_id:
            _logger.warning("Environment or employee_id not provided to TimePairingEngine. Cannot get calendar intervals.")
            return []
        
        employee = self.env["hr.employee"].browse(self.employee_id)
        if not employee or not employee.exists():
            _logger.warning("Employee %s not found. Cannot get calendar intervals.", self.employee_id)
            return []

        # Usar el método get_calendar_for_date para obtener el calendario aplicable
        # para cada día en el rango
        current_date = self.date_from.date()
        all_intervals = []
        while current_date <= self.date_to.date():
            calendar = self.env["resource.calendar"].get_calendar_for_date(employee.id, current_date)
            if calendar and calendar.exists():
                # _attendance_intervals_batch devuelve los intervalos ya fusionados para Cross Day
                # El tercer elemento del tuple (attendance_record) es crucial para vincular
                intervals_batch = calendar._attendance_intervals_batch(
                    datetime.combine(current_date, time.min).replace(tzinfo=pytz.utc),
                    datetime.combine(current_date + timedelta(days=1), time.min).replace(tzinfo=pytz.utc) - timedelta(microseconds=1),
                    resources=employee.resource_id # Asegurarse de pasar el recurso si existe
                ).get(employee.resource_id.id if employee.resource_id else False, [])
                
                # Expandir con tolerancias
                for start, stop, attendance_record in intervals_batch:
                    # Las tolerancias se obtienen del attendance_record original
                    tolerance_before = timedelta(hours=attendance_record.tolerance_before)
                    tolerance_after = timedelta(hours=attendance_record.tolerance_after)
                    
                    all_intervals.append({
                        "start": start,
                        "stop": stop,
                        "expanded_start": start - tolerance_before,
                        "expanded_stop": stop + tolerance_after,
                        "attendance_record_id": attendance_record.id,
                        "day_period": attendance_record.day_period,
                        "expected_hours": (stop - start).total_seconds() / 3600.0
                    })
            current_date += timedelta(days=1)
        
        self.calendar_intervals = sorted(all_intervals, key=lambda x: x["start"])
        _logger.info("Generated calendar intervals: %s", self.calendar_intervals)
        return self.calendar_intervals

    # -------------------------------------------------------
    # STEP 3 — pair punches (REDISEÑADO CON CONTEXTO DE CALENDARIO)
    # -------------------------------------------------------

    # Duración por defecto del almuerzo en horas
    DEFAULT_LUNCH_HOURS = 1.0

    def _pair_sequence(self, punches):
        """
        Algoritmo de emparejamiento usando intervalos de calendario como guía.
        
        Args:
            punches (list): Lista de datetime de las marcas.
            
        Returns:
            list: Lista de diccionarios con {check_in, check_out, has_lunch, lunch_duration, expected_hours, auto_closed, auto_close_reason, confidence_score}
        """
        if not punches:
            return []

        paired_attendances = []
        punches_to_process = list(punches) # Copia para poder modificarla

        # Asegurarse de que los intervalos del calendario estén cargados
        if not self.calendar_intervals:
            self._get_calendar_work_intervals()

        for interval in self.calendar_intervals:
            # Filtrar punches que caen dentro de la ventana expandida del intervalo
            # Y que no han sido procesados ya en un turno anterior
            current_interval_punches = sorted([
                p for p in punches_to_process 
                if interval["expanded_start"] <= p <= interval["expanded_stop"]
            ])

            if not current_interval_punches:
                # No hay punches para este turno planificado, generar asistencia auto-cerrada
                paired_attendances.append(self._create_autoclosed_attendance(interval, "window"))
                continue

            # Eliminar punches procesados del pool para evitar duplicados
            punches_to_process = [p for p in punches_to_process if p not in current_interval_punches]

            check_in = current_interval_punches[0]
            check_out = current_interval_punches[-1]
            
            # Lógica de almuerzo - simplificada para este rediseño, asumir 1 hora por defecto
            lunch_duration = self.DEFAULT_LUNCH_HOURS

            # Calcular duración total del turno de los punches
            punches_total_duration = (check_out - check_in).total_seconds() / 3600.0
            
            # Determinar si el turno fue auto-cerrado
            auto_closed = False
            auto_close_reason = False
            confidence_score = 0.0

            # Si solo hay un punch, es un check-in abierto
            if len(current_interval_punches) == 1:
                paired_attendances.append({
                    "check_in": check_in,
                    "check_out": False, # Mantenerlo abierto
                    "has_lunch": False,
                    "lunch_duration": 0.0,
                    "expected_hours": interval["expected_hours"],
                    "auto_closed": False, # No se cierra solo por un punch
                    "auto_close_reason": False,
                    "confidence_score": 0.5 # Baja confianza
                })
                continue # No procesar further, dejar abierto

            # Si el último punch cae fuera de la ventana o hay un exceso de horas
            if (check_out > interval["expanded_stop"] or 
                    punches_total_duration > self.max_shift.total_seconds() / 3600.0):
                auto_closed = True
                auto_close_reason = "timeout"
                check_out = min(check_out, interval["stop"] + timedelta(hours=self.max_shift.total_seconds() / 3600.0))
                confidence_score = 0.6 # Menos confianza por cierre automático
            else:
                confidence_score = 0.9 # Alta confianza

            paired_attendances.append({
                "check_in": check_in,
                "check_out": check_out,
                "has_lunch": True, # Asumimos almuerzo si el turno tiene duración
                "lunch_duration": lunch_duration,
                "expected_hours": interval["expected_hours"],
                "auto_closed": auto_closed,
                "auto_close_reason": auto_close_reason,
                "confidence_score": confidence_score
            })

        return paired_attendances

    def _create_autoclosed_attendance(self, interval, reason):
        """
        Crea un registro de asistencia auto-cerrado cuando no hay punches.
        """
        return {
            "check_in": interval["start"],
            "check_out": interval["stop"], # Se cierra al final de la ventana esperada
            "has_lunch": False,
            "lunch_duration": 0.0,
            "expected_hours": interval["expected_hours"],
            "auto_closed": True,
            "auto_close_reason": reason,
            "confidence_score": 0.3 # Muy baja confianza
        }

    # -------------------------------------------------------
    # PUBLIC METHOD
    # -------------------------------------------------------

    def pair(self):

        cleaned = self._remove_duplicates()

        return self._pair_sequence(cleaned)

