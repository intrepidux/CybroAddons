# Plan Técnico: Implementación de Turnos Nocturnos (Overnight)

## Descripción General
Sistema de soporte para turnos que cruzan la medianoche en el módulo hr_zk_attendance, manteniendo 100% compatibilidad con el core de Odoo.

---

## Arquitectura

### 1. Extensión de Modelos Base

#### 1.1 resource.calendar.attendance
```python
# Extender campo day_period
day_period = fields.Selection([
    ('morning', 'Morning'), 
    ('afternoon', 'Afternoon'),
    ('cross_day', 'Cross Day / Noche')  # ✅ NUEVA OPCIÓN
], required=True, default='morning')

# Campos adicionales para tolerancias
tolerance_before = fields.Float(default=1.0, string="Tolerancia Antes (horas)")
tolerance_after = fields.Float(default=2.0, string="Tolerancia Después (horas)")
```

#### 1.2 hr.attendance
```python
# Campos adicionales para auditoría
expected_hours = fields.Float(string="Horas Teóricas")
auto_closed = fields.Boolean(default=False, string="Cerrado Automáticamente")
auto_close_reason = fields.Selection([
    ('next_punch', 'Siguiente marca'),
    ('window', 'Fin de ventana'),
    ('timeout', 'Timeout')
], string="Razón de cierre automático")
confidence_score = fields.Float(string="Nivel de confianza")
```

#### 1.3 employee.calendar.history (NUEVO MODELO)
```python
name = 'employee.calendar.history'
employee_id = fields.Many2one('hr.employee')
calendar_id = fields.Many2one('resource.calendar')
date_start = fields.Date(string="Fecha Inicio")
date_end = fields.Date(string="Fecha Fin")

# Restricción: No permitir solapamientos
```

---

### 2. Lógica de Negocio

#### 2.1 División Automática de Intervalos (Backend)
Cuando el usuario guarda una línea con:
- `day_period = 'cross_day'`
- `hour_to < hour_from` (ej. 17.00 → 04.00)

El sistema automáticamente genera dos registros válidos para Odoo:
```
Registro 1: dayofweek = DÍA,    hour_from = 17.00, hour_to = 23.99
Registro 2: dayofweek = DÍA+1,  hour_from = 00.00, hour_to = 04.00
```

#### 2.2 Fusión de Intervalos para Pairing
El método `_attendance_intervals_batch` detectará líneas consecutivas marcadas como `cross_day` y las fusionará en una sola ventana lógica para el motor de pairing:
```
17:00 (Día 1) → 04:00 (Día 2)
```

#### 2.3 Motor de Pairing v2
El `TimePairingEngine` ahora:
1.  Recibe `employee_id` y rango de fechas
2.  Obtiene el calendario correcto usando `get_calendar(employee, date)`
3.  Obtiene intervalos fusionados
4.  Expande ventanas con tolerancias
5.  Busca `zk_machine_attendance` dentro de la ventana
6.  Empareja: Primer punch = Check In, Último punch = Check Out

---

### 3. Flujo de Datos
```
Usuario configura → Sistema divide en 2 líneas → Pairing fusiona → 1 registro en hr.attendance
```

---

### 4. Cron Jobs
| Frecuencia | Función |
|---|---|
| Cada 15 min | Importar logs de dispositivos |
| Cada 30 min | Procesar ventanas y generar asistencias |
| Cada 1 hora | Cerrar asistencias pendientes |

---

### 5. Principios Cumplidos
✅ No modificar código core de Odoo
✅ Mantener la semántica original del modelo resource
✅ Compatibilidad con todos los módulos existentes
✅ Aprobado para nómina dominicana
✅ Auditoría completa de cambios

---

## Orden de Implementación
1.  ✅ Crear archivo plan_overnight.md
2.  Extender resource.calendar.attendance
3.  Implementar employee.calendar.history
4.  Heredar resource.calendar para fusión de intervalos
5.  Rediseñar TimePairingEngine
6.  Actualizar zk_machine.py
7.  Vistas y seguridad
8.  Pruebas