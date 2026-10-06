# -*- coding: utf-8 -*-
###################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2020-TODAY Cybrosys Technologies(<http://www.cybrosys.com>).
#    Author: cybrosys(<https://www.cybrosys.com>)
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
import pytz
import sys
from datetime import datetime as dt_datetime, time as dt_time, timedelta
import logging
import binascii

from . import zklib
from .zkconst import *
from struct import unpack
from odoo import api, fields, models
from odoo import _
from odoo.exceptions import UserError, ValidationError
from .attendance_pairing_engine import TimePairingEngine

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Please Install pyzk library.")

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    device_id = fields.Char(string='Biometric Device ID')
    lunch_duration_deducted = fields.Float(
        string='Duración almuerzo deducida (horas)',
        digits=(12, 2),
        default=1.0,
        help='Duración del almuerzo detectada en horas. Si es 0, se deducirá 1 hora automáticamente en worked_hours.'
    )

    # Sobreescribir worked_hours para que calcule horas netas (deduciendo almuerzo)
    @api.depends('check_in', 'check_out', 'lunch_duration_deducted')
    def _compute_worked_hours(self):
        """Calcula las horas trabajadas deduciendo el tiempo de almuerzo"""
        for record in self:
            if not record.check_in or not record.check_out:
                record.worked_hours = 0.0
                continue
            
            # Calcular horas totales
            check_in = fields.Datetime.from_string(record.check_in)
            check_out = fields.Datetime.from_string(record.check_out)
            delta = check_out - check_in
            total_hours = delta.total_seconds() / 3600.0
            
            # Deducir tiempo de almuerzo (por defecto 1 hora si no está especificado)
            lunch_deduction = record.lunch_duration_deducted if record.lunch_duration_deducted > 0 else 1.0
            
            # Las horas netas no pueden ser negativas
            net_hours = max(0.0, total_hours - lunch_deduction)
            record.worked_hours = net_hours


class ZkMachine(models.Model):
    _name = 'zk.machine'
    
    name = fields.Char(string='Machine IP', required=True)
    port_no = fields.Integer(string='Port No', required=True)
    address_id = fields.Many2one('res.partner', string='Working Address')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)

    def device_connect(self, zk):
        try:
            _logger.info("Attempting to connect to device")
            conn = zk.connect()
            _logger.info("Connection successful")
            return conn
        except Exception as e:
            _logger.error("Error connecting to device: %s", e)
            return False

    def test_connection(self):

        self.ensure_one()

        try:
            machine_ip = self.name
            zk_port = self.port_no
            timeout = 30

            zk = ZK(
                machine_ip,
                port=zk_port,
                timeout=timeout,
                password=0,
                force_udp=False,
                ommit_ping=True
            )

            conn = self.device_connect(zk)

            if conn:
                conn.disconnect()

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Conexión Exitosa'),
                        'message': _('El dispositivo respondió correctamente.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Fallida'),
                    'message': _('No fue posible conectarse al dispositivo. Verifique IP, puerto y red.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }

        except Exception as e:

            _logger.error("ZK connection error: %s", e)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error de Conexión'),
                    'message': _('Connection failed: %s (dep pyzk)') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def check_connection(self):
        """Check connection without raising UserError, returns True/False"""
        for info in self:
            try:
                machine_ip = info.name
                zk_port = info.port_no
                timeout = 30
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=True)
                conn = self.device_connect(zk)
                if conn:
                    conn.disconnect()
                    return True
                else:
                    return False
            except Exception as e:
                _logger.error("Connection check failed: %s", e)
                return False
    
    def handle_punch_type(self, punch_value):
        """Convert punch value to a valid selection value"""
        # Convert to string if it's not already
        punch_str = str(punch_value)
        
        # Check if the punch value is in the allowed selection values
        allowed_values = ['0', '1', '2', '3', '4', '5', '255']
        if punch_str in allowed_values:
            return punch_str
        else:
            # Default to '0' (unknown) for unknown values
            return '255'
            
    def handle_attendance_type(self, attendance_value):
        """Convert attendance type value to a valid selection value"""
        # Convert to string if it's not already
        attendance_str = str(attendance_value)
        
        # Check if the attendance value is in the allowed selection values
        allowed_values = ['1', '15', '2', '3', '4', '16']
        if attendance_str in allowed_values:
            return attendance_str
        else:
            # Default to '1' (Unknown) for unknown values
            return '16'
    
    def clear_attendance(self):
        for info in self:
            try:
                machine_ip = info.name
                zk_port = info.port_no
                timeout = 30
                try:
                    zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=True)
                except NameError:
                    raise UserError(_("Please install it with 'pip3 install pyzk'."))
                conn = self.device_connect(zk)
                if conn:
                    conn.enable_device()
                    clear_data = zk.get_attendance()
                    if clear_data:
                        # conn.clear_attendance()
                        self._cr.execute("""delete from zk_machine_attendance""")
                        conn.disconnect()
                        raise UserError(_('Attendance Records Deleted.'))
                    else:
                        raise UserError(_('Unable to clear Attendance log. Are you sure attendance log is not empty.'))
                else:
                    raise UserError(
                        _('Unable to connect to Attendance Device. Please use Test Connection button to verify.'))
            except:
                raise ValidationError(
                    'Unable to clear Attendance log. Are you sure attendance device is connected & record is not empty.')

    def getSizeUser(self, zk):
        """Checks a returned packet to see if it returned CMD_PREPARE_DATA,
        indicating that data packets are to be sent

        Returns the amount of bytes that are going to be sent"""
        command = unpack('HHHH', zk.data_recv[:8])[0]
        if command == CMD_PREPARE_DATA:
            size = unpack('I', zk.data_recv[8:12])[0]
            print("size", size)
            return size
        else:
            return False

    def zkgetuser(self, zk):
        """Start a connection with the time clock"""
        try:
            users = zk.get_users()
            print(users)
            return users
        except:
            return False

    # ============================================================
    # FUNCIONES AUXILIARES DE CONEXIÓN
    # ============================================================

    def _create_zk_connection(self, machine_ip, zk_port, timeout=30):
        """Crear conexión ZK al dispositivo"""
        try:
            zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=True)
            conn = self.device_connect(zk)
            return conn
        except Exception as e:
            _logger.error("Error creating ZK connection: %s", e)
            return False

    def _get_employee_dict(self):
        """Construir diccionario de empleados por device_id"""
        self._cr.execute("SELECT id, device_id FROM hr_employee WHERE device_id IS NOT NULL")
        rows = self._cr.fetchall()
        return {str(row[1]): row[0] for row in rows}

    def _convert_timestamp_to_utc(self, timestamp):
        """Convertir timestamp del dispositivo a UTC string"""
        atten_time = timestamp
        atten_time = dt_datetime.strptime(atten_time.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
        
        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')
        local_dt = local_tz.localize(atten_time, is_dst=None)
        
        utc_dt = local_dt.astimezone(pytz.utc)
        utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        atten_time = dt_datetime.strptime(utc_dt, "%Y-%m-%d %H:%M:%S")
        atten_time_str = fields.Datetime.to_string(atten_time)
        
        return atten_time, atten_time_str

    def _check_attendance_exists(self, device_id, punching_time):
        """Verificar si attendance ya existe en zk_machine_attendance"""
        self._cr.execute("""
            SELECT COUNT(*) FROM zk_machine_attendance
            WHERE device_id = %s AND punching_time = %s
        """, [device_id, punching_time])
        return self._cr.fetchone()[0] > 0

    # ============================================================
    # FUNCIONES DE HORARIO DEL EMPLEADO
    # ============================================================

    def _get_employee_calendar_id(self, employee_id, check_in_date=None):
        """Return calendar id for employee, optionally for a specific date."""
        if check_in_date:
            calendar = self.env['resource.calendar'].get_calendar_for_date(
                employee_id, check_in_date
            )
            return calendar.id if calendar else False
        self._cr.execute("""
            SELECT resource_calendar_id FROM hr_employee
            WHERE id = %s
        """, [employee_id])
        result = self._cr.fetchone()
        return result[0] if result else False

    def _get_calendar_work_hours(self, calendar_id, date):
        """Obtener horas de trabajo del calendario para una fecha específica"""
        if not calendar_id:
            return None
        
        # El campo dayofweek es de tipo character, convertir a string
        dayofweek = str(date.weekday())
            
        # Buscar intervalos de trabajo para esa fecha
        self._cr.execute("""
            SELECT hour_from, hour_to 
            FROM resource_calendar_attendance 
            WHERE calendar_id = %s 
            AND dayofweek = %s
            AND (date_from IS NULL OR date_from <= %s)
            AND (date_to IS NULL OR date_to >= %s)
            ORDER BY hour_from DESC
            LIMIT 1
        """, [calendar_id, dayofweek, date, date])
        
        result = self._cr.fetchone()
        if result:
            return {'hour_from': result[0], 'hour_to': result[1]}
        return None

    def _close_pending_attendances(self, punches_by_emp_date=None):
        """
        Cerrar attendantas pendientes basándose en el horario del empleado.
        Solo cierra si NO hay un Check-Out estimado para ese día.
        
        :param punches_by_emp_date: Diccionario con punches {(emp_id, fecha): [(datetime_utc, local_hour)]}
        """
        att_obj = self.env['hr.attendance']
        
        # Buscar attendantas abiertas
        open_attendances = att_obj.search([
            ('check_out', '=', False)
        ])
        
        closed_count = 0
        skipped_already_closed = 0
        
        for att in open_attendances:
            if not att.check_in:
                continue
                
            # Obtener fecha del check-in
            check_in_date = fields.Datetime.from_string(att.check_in).date()
            today = fields.Date.today()
            
            # Solo cerrar si es de días anteriores (no el día de hoy)
            if check_in_date >= today:
                continue
            
            emp_id = att.employee_id.id
            
            # Si tenemos punches del día, verificar si ya hay Check-Out estimado
            if punches_by_emp_date:
                key = (emp_id, check_in_date)
                if key in punches_by_emp_date:
                    all_punches = punches_by_emp_date[key]
                    # Contar punches de la tarde (hora local >= 12)
                    afternoon_punches = [p for p in all_punches if len(p) >= 2 and p[1] >= 12]
                    if len(afternoon_punches) >= 1:
                        # Ya hay punch de tarde (Check-Out) en los datos
                        skipped_already_closed += 1
                        _logger.info("Skipping attendance %s for employee %s - already has Check-Out in punches", 
                                   att.id, emp_id)
                        continue
            
            # Obtener calendario del empleado (siempre existe)
            calendar_id = self._get_employee_calendar_id(emp_id, check_in_date)
            
            # Obtener hora de salida del calendario
            work_hours = self._get_calendar_work_hours(calendar_id, check_in_date)
            
            if work_hours:
                # Usar hora de salida del calendario
                checkout_hour = int(work_hours['hour_to'])
                checkout_minute = int((work_hours['hour_to'] % 1) * 60)
            else:
                # Fallback: 17:00 si no hay horario definido para ese día
                checkout_hour = 17
                checkout_minute = 0
            
            # Crear datetime de checkout
            checkout_dt = dt_datetime.combine(
                check_in_date, 
                dt_time(checkout_hour, checkout_minute, 0)
            )
            checkout_str = fields.Datetime.to_string(checkout_dt)
            
            # Cerrar la asistencia
            try:
                att.write({'check_out': checkout_str})
                closed_count += 1
                _logger.info("Closed attendance %s for employee %s at %s (calendar based)", 
                           att.id, emp_id, checkout_str)
            except Exception as e:
                _logger.error("Error closing attendance %s: %s", att.id, e)
        
        _logger.info("Close pending: %s closed, %s skipped (already has Check-Out)", 
                    closed_count, skipped_already_closed)
        
        return closed_count

    # ============================================================
    # FUNCIONES DE LÓGICA DE NEGOCIO
    # ============================================================

    def _pair_attendance(self, employee_id, date_from, date_to, punches):
        engine = TimePairingEngine(
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            punches=punches,
            env=self.env
        )
        return engine.pair()


  

    def _create_zk_record(self, emp_id, device_id, atten_time_str, punch_type, attendance_status, address_id):
        """Crear registro en zk_machine_attendance"""
        zk_attendance = self.env['zk.machine.attendance']
        
        create_vals = {
            'employee_id': emp_id,
            'device_id': device_id,
            'check_in': atten_time_str,
            'attendance_type': self.handle_attendance_type(attendance_status),
            'punch_type': punch_type,
            'punching_time': atten_time_str,
        }
        
        if address_id:
            create_vals['address_id'] = address_id.id
            
        return zk_attendance.with_context(tracking_disable=True).create(create_vals)

    @api.model
    def cron_download(self):
        return super().cron_download()
    

    def download_attendance(self, silent=False):

        self.ensure_one()

        _logger.info("++++++++++++Download Attendance Executed (silent=%s)++++++++++++++++++++++", silent)

        zk_attendance = self.env['zk.machine.attendance']

        result_msg = False

        for info in self:

            if getattr(info, 'device_kind', 'physical') == 'kiosk':
                _logger.info("Skipping kiosk device %s in download_attendance", info.id)
                continue

            if not self.check_connection():
                error_msg = _('Connection check failed. Unable to connect to the device.')
                if not silent:
                    raise UserError(error_msg)
                _logger.error("Download failed for device %s: %s", info.name, error_msg)
                continue

            machine_ip = info.name
            zk_port = info.port_no
            timeout = 30

            _logger.info("Connecting to device %s:%s", machine_ip, zk_port)

            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=True)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            except Exception as e:
                raise UserError(_("Error creating ZK instance: %s") % e)

            conn = self.device_connect(zk)

            if not conn:
                raise UserError(_('Unable to connect, please check the parameters and network connections.'))

            try:
                users = conn.get_users()
            except Exception as e:
                _logger.warning("Error getting users: %s", e)
                users = []

            try:
                attendance = conn.get_attendance()
            except Exception as e:
                _logger.error("Error getting attendance: %s", e)
                attendance = []

            if not attendance:
                raise UserError(_('Unable to get the attendance log, please try again later.'))

            _logger.info("Device returned %s attendance records", len(attendance))

            # ============================================================
            # MAP EMPLOYEES
            # ============================================================

            self._cr.execute("SELECT id, device_id FROM hr_employee WHERE device_id IS NOT NULL")
            emp_dict = {str(device_id): emp_id for emp_id, device_id in self._cr.fetchall()}

            # ============================================================
            # PREPARE STRUCTURES
            # ============================================================

            punches_by_emp_date = {}
            created_zk = 0
            created_hr = 0
            updated_hr = 0
            skipped = 0

            # Usar zona horaria del usuario actual o America/Santo_Domingo como fallback
            user_tz = self.env.user.tz or 'America/Santo_Domingo'
            device_tz = pytz.timezone(user_tz)

            # ============================================================
            # NORMALIZE ALL PUNCHES
            # ============================================================

            normalized_records = []

            for each in attendance:

                user_id_str = str(each.user_id)

                if user_id_str not in emp_dict:
                    skipped += 1
                    continue

                emp_id = emp_dict[user_id_str]

                atten_time = each.timestamp
                atten_time = dt_datetime.strptime(
                    atten_time.strftime('%Y-%m-%d %H:%M:%S'),
                    '%Y-%m-%d %H:%M:%S'
                )

                local_dt = device_tz.localize(atten_time, is_dst=None)
                local_hour = local_dt.hour
                utc_dt = local_dt.astimezone(pytz.utc)

                atten_time_utc = dt_datetime.strptime(
                    utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "%Y-%m-%d %H:%M:%S"
                )

                atten_time_str = fields.Datetime.to_string(atten_time_utc)

                emp_rec = self.env['hr.employee'].browse(emp_id)
                work_date = self._work_date_for_employee(emp_rec, atten_time_utc)

                normalized_records.append({
                    "emp_id": emp_id,
                    "user_id_str": user_id_str,
                    "datetime": atten_time_utc,
                    "datetime_str": atten_time_str,
                    "local_hour": local_hour,
                    "work_date": work_date,
                    "raw": each
                })

                key = (emp_id, work_date)
                punches_by_emp_date.setdefault(key, []).append((atten_time_utc, local_hour))

            _logger.info("Grouped punches for %s employee-days", len(punches_by_emp_date))

            # ============================================================
            # PROCESS RECORDS - USANDO TimePairingEngine
            # ============================================================

            # Primero, crear todos los registros ZK (raw)
            for rec in normalized_records:
                emp_id = rec["emp_id"]
                user_id_str = rec["user_id_str"]
                atten_time_str = rec["datetime_str"]
                each = rec["raw"]

                # Verificar si ya existe el registro
                self._cr.execute("""
                    SELECT COUNT(*) FROM zk_machine_attendance
                    WHERE device_id=%s AND punching_time=%s
                """, [user_id_str, atten_time_str])

                exists = self._cr.fetchone()[0]

                if not exists:
                    try:
                        create_vals = {
                            'employee_id': emp_id,
                            'device_id': user_id_str,
                            'check_in': atten_time_str,
                            'attendance_type': self.handle_attendance_type(each.status),
                            'punch_type': self.handle_punch_type(each.punch),
                            'punching_time': atten_time_str,
                        }

                        if info.address_id:
                            create_vals['address_id'] = info.address_id.id

                        zk_attendance.with_context(tracking_disable=True).create(create_vals)
                        created_zk += 1

                    except Exception as e:
                        _logger.error("Error creating ZK attendance record: %s", e)
                else:
                    skipped += 1

            for (emp_id, work_date), punches_list in punches_by_emp_date.items():
                punches_datetimes_raw = [p[0] for p in punches_list]
                _logger.info(
                    "Processing employee %s work_date %s with punches: %s",
                    emp_id, work_date, punches_datetimes_raw,
                )
                sync_result = self._apply_pairing_to_hr(
                    emp_id, work_date, punches_datetimes=punches_datetimes_raw,
                )
                created_hr += sync_result.get('created', 0)
                updated_hr += sync_result.get('updated', 0)

            conn.disconnect()

            # ============================================================
            # AUTO CLOSE PENDING ATTENDANCE (AHORA INTEGRADO EN PAIRING)
            # ============================================================

            closed_pending = 0  # Ya no es necesario un cierre separado, el pairing lo maneja

            updated_hr += closed_pending

            self._cr.commit()

            result_msg = (
                "Asistencia descargada: "
                "ZK:%s creados, HR:%s creados, %s actualizados "
                "(%s cerradas automáticamente)"
            ) % (
                created_zk,
                created_hr,
                updated_hr,
                closed_pending
            )

            _logger.info(result_msg)

        if not silent and result_msg:

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Descarga Completada",
                    "message": result_msg,
                    "sticky": True,
                    "type": "success"
                }
            }

        return True
