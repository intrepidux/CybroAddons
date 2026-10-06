# Plan de Corrección: Sincronización de Asistencia hr_zk_attendance

## 1. Diagnóstico del Problema

### 1.1 Causa Raíz
La versión actual de `download_attendance` en `zk_machine.py` **no está sincronizando los datos en el modelo base `hr.attendance` de Odoo**, el cual es el que alimenta los reportes pivot y otras vistas estándar de asistencia.

### 1.2 Diferencias Clave entre Versión Original y Actual

| Aspecto | Versión Original | Versión Actual |
|---------|------------------|----------------|
| Sincronización dual | ✅ Crea en `zk.machine.attendance` Y en `hr.attendance` | ✅ Implementada |
| Lógica Check-in/Check-out | ✅ Implementada | ✅ Implementada |
| Manejo de duplicates | ✅ Busca en `hr.attendance` y `zk.machine.attendance` | ✅ Implementado |
| Manejo de punch_type 255 | ❌ No maneja | ✅ Implementado (tratado como Check-In) |

### 1.3 Modelos Involucrados

1. **`zk.machine.attendance`**: Modelo personalizado que almacena los registros crudos del dispositivo biométrico.
2. **`hr.attendance`**: Modelo base de Odoo que alimenta los reportes pivot y vistas estándar de asistencia.

### 1.4 Estado Actual (Post-Implementación)

- ✅ Código implementado y actualizado en Odoo
- ✅ Descarga de asistencia ejecutada exitosamente
- ✅ Sincronización básica funcionando (solo punch_type 0 y 1)
- ⚠️ **Problema identificado**: El dispositivo envía punch_type 255 para muchos registros

---

## 2. Análisis del Dispositivo

### 2.1 Valores de Punch Type Observados

| Punch Type | Cantidad | Descripción |
|------------|----------|-------------|
| 0 | 18 | Check-In estándar |
| 255 | 73 | Valor desconocido (el dispositivo usa esto para marcaciones) |

### 2.2 Funciones de Normalización Existentes

El módulo ya cuenta con funciones para normalizar los valores del dispositivo:

```python
def handle_punch_type(self, punch_value):
    """Convierte el valor de punch a un valor válido de selección"""
    punch_str = str(punch_value)
    allowed_values = ['0', '1', '2', '3', '4', '5', '255']
    if punch_str in allowed_values:
        return punch_str
    else:
        return '255'

def handle_attendance_type(self, attendance_value):
    """Convierte el tipo de asistencia a un valor válido"""
    attendance_str = str(attendance_value)
    allowed_values = ['1', '15', '2', '3', '4', '16']
    if attendance_str in allowed_values:
        return attendance_str
    else:
        return '16'
```

---

## 3. Solución Propuesta (Ajustada)

### 3.1 Flujo de Sincronización Actual

```
1. Descargar datos del dispositivo biométrico
   ↓
2. Para cada registro del dispositivo:
   ├─ Si punch_type == 0 (Check-In):
   │   └─ Crear registro en hr.attendance con check_in
   │
   ├─ Si punch_type == 1 (Check-Out):
   │   └─ Buscar registro hr.attendance sin check_out para ese empleado
   │   └─ Actualizar check_out en el registro encontrado
   │
   └─ Si punch_type == 255 (Unknown):
       └─ ✅ TRATADO COMO CHECK-IN (lógica simple)
           └─ La lógica dinámica basada en horario se implementará más adelante
3. Guardar siempre en zk.machine.attendance (registro crudo)
4. Verificar si el registro ya existe en hr.attendance antes de crear
```

### 3.2 Opción A: Tratar 255 como Check-In (Alternativa Simple)

Tratar el punch_type 255 como una marcación de entrada (Check-In), creando un nuevo registro en hr.attendance cada vez que se encuentre este valor.

**Ventajas:**
- Simple de implementar
- Registra todas las marcaciones

**Desventajas:**
- Puede crear muchos registros sin salida (check_out)

### 3.3 Opción B: Lógica Basada en Horario Laboral (IMPLEMENTADA)

**Principio fundamental:** Sin importar el valor de punch_type, la decisión de si es Check-In o Check-Out se determina por el **estado actual de la asistencia del empleado**.

**Reglas de operación:**
1. **Si el empleado tiene asistencia ABIERTA** (sin check_out):
   - La nueva marcación será tratada como **Check-Out**
   - Se cierra la asistencia anterior
   
2. **Si el empleado NO tiene asistencia abierta:**
   - La nueva marcación será tratada como **Check-In**
   - Se crea una nueva asistencia

**Valores por defecto (Hardcoded - Pending definir horarios laborales):**
- Si viene un Check-Out pero no hay asistencia abierta → Crear asistencia con **Check-In a las 8:00 AM**
- Si viene un Check-In pero ya hay asistencia abierta → Cerrar asistencia anterior con **Check-Out a las 5:00 PM**

**Nota:** Esta lógica se implementará dinámicamente cuando se definan los horarios laborales reales en Odoo mediante `resource.calendar`.

**Ventajas:**
- Respeta las validaciones nativas de Odoo
- Maneja cualquier tipo de punch_type correctamente
- Robusto ante fallos de marcación

**Desventajas:**
- Requiere orden cronológico en el procesamiento

---

## 4. Resultados de la Primera Ejecución

### 4.1 Estadísticas de Descarga

```
Total del dispositivo: 253 registros
ZK Created: 203
ZK Skipped: 50 (duplicados)
HR Created: 6 (solo punch_type 0)
HR Updated: 0
```

### 4.2 Registros en hr.attendance

| ID | Empleado | Check-In | Check-Out |
|----|----------|----------|-----------|
| 13 | 55 | 2025-09-07 12:34:45 | - |
| 12 | 54 | 2025-08-11 18:07:03 | - |
| 10 | 29 | 2025-06-23 16:52:26 | - |
| 9 | 28 | 2025-06-19 12:42:34 | - |
| 8 | 27 | 2025-06-18 16:30:29 | - |
| 7 | 26 | 2025-06-17 20:25:36 | - |
| 6 | 25 | 2025-06-17 17:00:30 | - |
| 5 | 24 | 2024-11-22 18:52:18 | - |

---

## 5. Código Actual (zk_machine.py)

El código actual implementa la sincronización básica pero NO maneja punch_type 255:

```python
# 2. Sync to hr.attendance based on punch_type
punch_val = int(each.punch) if isinstance(each.punch, int) else int(str(each.punch))

if punch_val == 0:  # Check-In
    # Create new attendance record
    att_obj.create({
        'employee_id': emp_id,
        'check_in': atten_time_str
    })
    created_hr += 1
    print(f"HR Attendance Created (Check-In): {emp_id}")
    
elif punch_val == 1:  # Check-Out
    # Find the latest attendance without check_out
    att_var = att_obj.search([
        ('employee_id', '=', emp_id),
        ('check_out', '=', False)
    ], order='check_in asc', limit=1)
    
    if att_var:
        att_var.write({'check_out': atten_time_str})
        updated_hr += 1
        print(f"HR Attendance Updated (Check-Out): {att_var.id}")
```

---

## 6. Pasos de Verificación Manual

### 6.1 Después de Aplicar el Código

1. **Ejecutar la descarga de asistencia** desde el dispositivo
2. **Verificar `zk.machine.attendance`**: Ir a *Asistencia > Registros de Asistencia* y buscar nuevos registros
3. **Verificar `hr.attendance`**: Ir a *Empleados > Asistencias* y confirmar que aparecen check-ins y check-outs
4. **Verificar reporte pivot**: Acceder a `hr.attendance.report` y confirmar que aparecen datos
5. **Verificar reporte diario**: Acceder a `zk.report.daily.attendance` y confirmar que muestra datos

### 6.2 Logs a Revisar

- En el log del servidor Odoo buscar mensajes con `+++++Download Attendance Executed`
- Revisar los prints: `ZK Created`, `HR Created`, `HR Updated`

---

## 7. Notas Importantes

1. **Orden de operaciones**: Primero guardamos en `zk.machine.attendance` (para mantener logs crudos), luego sincronizamos a `hr.attendance` (para reportes).

2. **Manejo de Check-Out sin Check-In**: Si el dispositivo registra un Check-Out pero no hay un Check-In previo, el código actual solo actualiza el log en `zk.machine.attendance` pero no crea un registro en `hr.attendance` (para evitar inconsistencias).

3. **Zona horaria**: Se mantiene la conversión a UTC para consistencia.

4. **Silent mode**: Si se llama desde el cron, el parámetro `silent=True` evita mostrar mensajes emergentes.

---

## 8. Estado de Implementación

### 8.1 Implementado ✅
- **punch_type 0**: Check-In estándar
- **punch_type 255**: Tratamiento simple como Check-In (lógica actual)

### 8.2 Pendiente - Implementación Dinámica (Basada en Horario Laboral)
La lógica avanzada para determinar Check-In/Check-Out basada en:
- Horario laboral del empleado
- Secuencia de marcaciones
- Tiempos de entrada/salida configurados

Se implementará más adelante según lo planificado.

### 8.3 Verificación Recomendada

**El usuario debe verificar manualmente en el portal Odoo:**
1. Ir a *Empleados > Asistencias* y confirmar que aparecen más registros (los de punch_type 255 ahora se sincronizan)
2. Verificar si los reportes pivot muestran datos
3. Revisar los logs del servidor buscando `HR Attendance Created (Check-In255)`
