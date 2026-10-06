# Pseudocódigo: Sistema de Asistencia ZK Biometric

## Descripción General

Este documento describe el algoritmo para descargar y procesar datos de asistencia desde dispositivos biométricos ZK (huellas dactilares/facial) en Odoo 15.

> **Última actualización:** Marzo 2026
> **Versión:** 1.1

---

## Flujo General del Sistema

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Dispositivo ZK  │────>│  download_       │────>│ TimePairing     │
│ (Biométrico)    │     │  attendance()   │     │ Engine          │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          v
                         ┌──────────────────┐     ┌─────────────────┐
                         │ zk_machine_      │<────│ hr.attendance   │
                         │ attendance       │     │ (Asistencias)   │
                         └──────────────────┘     └─────────────────┘
```

---

## 1. Conexión al Dispositivo

### Parámetros de Conexión
| Campo | Descripción |
|-------|-------------|
| `machine_ip` | Dirección IP del dispositivo |
| `port_no` | Puerto de comunicación (default: 4370) |
| `timeout` | Tiempo de espera (default: 30 seg) |
| `password` | Contraseña del dispositivo (default: 0) |

### Pseudocódigo de Conexión

```
FUNCIÓN test_connection(machine_ip, zk_port)
    INICIO
        // Crear objeto ZK
        zk = ZK(machine_ip, port=zk_port, timeout=30)
        
        // Intentar conexión
        conn = zk.connect()
        
        SI conn EXISTE ENTONCES
            conn.disconnect()
            RETORNAR True
        SINO
            RETORNAR False
        FIN SI
    FIN
```

---

## 2. Motor de Emparejamiento (TimePairingEngine)

### Propósito
El `TimePairingEngine` es responsable de:
1. Eliminar punches duplicados
2. Emparejar entradas y salidas
3. Calcular duración del almuerzo

### Parámetros de Configuración

| Parámetro | Valor Default | Descripción |
|-----------|--------------|-------------|
| `duplicate_threshold_minutes` | 2 | Minutos entre punches para considerar duplicado |
| `min_pair_minutes` | 3 | Mínimo minutos para considerar un par válido |
| `max_shift_hours` | 16 | Máximo horas en un turno |
| `lunch_threshold_hours` | 3 | Horas mínimas para considerar pausa de almuerzo |
| `DEFAULT_LUNCH_HOURS` | 1.0 | Horas de almuerzo a deducir por defecto |

---

## 3. Algoritmo de Emparejamiento (PAIRING)

### Paso 1: Eliminar Duplicados

```
FUNCIÓN _remove_duplicates(punches)
    INICIO
        cleaned = []
        
        PARA CADA punch EN punches:
            SI cleaned ESTÁ VACÍO ENTONCES
                cleaned.agregar(punch)
            SINO
                diff = punch - cleaned[último]
                
                SI diff > 2 minutos ENTONCES
                    cleaned.agregar(punch)
                // SI diff <= 2 minutos: es duplicado, IGNORAR
            FIN SI
        FIN PARA
        
        RETORNAR cleaned
    FIN
```

### Paso 2: Emparejar Secuencia

```
FUNCIÓN _pair_sequence(punches)
    INICIO
        // CASO 1: Solo 1 punch (Asistencia abierta)
        SI punches.tamaño == 1 ENTONCES
            RETORNAR [{
                "check_in": punches[0],
                "check_out": NULO,
                "has_lunch": False,
                "lunch_duration": 0.0
            }]
        
        // CASO 2: 2 punches (Entrada + Salida)
        SI punches.tamaño == 2 ENTONCES
            RETORNAR [{
                "check_in": punches[0],
                "check_out": punches[1],
                "has_lunch": False,
                "lunch_duration": 1.0  // Deducir 1 hora por defecto
            }]
        
        // CASO 3: 4+ punches (Puede haber almuerzo)
        SI punches.tamaño >= 4 ENTONCES
            lunch_start = punches[1]   // Salida al almuerzo
            lunch_end = punches[2]     // Regreso del almuerzo
            lunch_duration = lunch_end - lunch_start
            
            // Validar duración del almuerzo
            SI lunch_duration > 10 minutos Y lunch_duration < 4 horas ENTONCES
                lunch_hours = convertir_a_horas(lunch_duration)
                RETORNAR [{
                    "check_in": punches[0],
                    "check_out": punches[último],
                    "has_lunch": True,
                    "lunch_duration": lunch_hours
                }]
        
        // CASO 4: 3 punches o duración inválida
        // Usar primer y último punch, deducir 1 hora por defecto
        RETORNAR [{
            "check_in": punches[0],
            "check_out": punches[último],
            "has_lunch": False,
            "lunch_duration": 1.0
        }]
    FIN
```

---

## 4. Ejemplos Detallados de Emparejamiento

### Ejemplo 1: Turno Normal con 4 Punches (Almuerzo Detectado)

**Escenario:** Empleado trabaja con horario de 8:00 AM a 5:00 PM con almuerzo de 1 hora

**Punches del dispositivo:**
```
Punch 1: 2026-03-15 08:00:00 (Entrada mañana)
Punch 2: 2026-03-15 12:00:00 (Salida almuerzo)
Punch 3: 2026-03-15 13:00:00 (Entrada almuerzo)
Punch 4: 2026-03-15 17:00:00 (Salida tarde)
```

**Paso 1: Eliminar duplicados**
```
Entrada: [08:00, 12:00, 13:00, 17:00]
No hay duplicados (diferencia > 2 minutos)
Salida: [08:00, 12:00, 13:00, 17:00]
```

**Paso 2: Emparejar**
```
- Cantidad: 4 (>= 4)
- lunch_start = punches[1] = 12:00
- lunch_end = punches[2] = 13:00
- lunch_duration = 13:00 - 12:00 = 1 hora

Validación: 1 hora > 10 min ✓ Y 1 hora < 4 horas ✓ = VÁLIDO
```

**Resultado:**
```json
{
  "check_in": "2026-03-15 08:00:00",
  "check_out": "2026-03-15 17:00:00",
  "has_lunch": true,
  "lunch_duration": 1.0
}
```

---

### Ejemplo 2: Turno sin Marca de Almuerzo (2 Punches)

**Escenario:** Empleado trabaja pero no registra punches de almuerzo

**Punches del dispositivo:**
```
Punch 1: 2026-03-15 08:30:00 (Entrada)
Punch 2: 2026-03-15 17:30:00 (Salida)
```

**Paso 1: Eliminar duplicados**
```
Entrada: [08:30, 17:30]
No hay duplicados
Salida: [08:30, 17:30]
```

**Paso 2: Emparejar**
```
- Cantidad: 2
- Usar primer y último punch
- Deducir 1 hora por defecto
```

**Resultado:**
```json
{
  "check_in": "2026-03-15 08:30:00",
  "check_out": "2026-03-15 17:30:00",
  "has_lunch": false,
  "lunch_duration": 1.0
}
```

**Cálculo de horas:**
```
Total: 17:30 - 08:30 = 9 horas
Deducir: 1 hora de almuerzo
Horas trabajadas: 9 - 1 = 8 horas
```

---

### Ejemplo 3: Duplicados (Empleado registra mismo punch 2 veces)

**Escenario:** El dispositivo registra el punch de entrada dos veces

**Punches del dispositivo:**
```
Punch 1: 2026-03-15 08:00:00
Punch 2: 2026-03-15 08:00:30  (duplicado - solo 30 seg después)
Punch 3: 2026-03-15 12:00:00
Punch 4: 2026-03-15 13:00:00
Punch 5: 2026-03-15 17:00:00
```

**Paso 1: Eliminar duplicados**
```
Umbral: 2 minutos

Punch 1: 08:00:00 → cleaned[08:00:00]
Punch 2: 08:00:30 → diff = 30 seg < 2 min → IGNORAR (duplicado)
Punch 3: 12:00:00 → diff = 4 horas > 2 min → AGREGAR
Punch 4: 13:00:00 → diff = 1 hora > 2 min → AGREGAR
Punch 5: 17:00:00 → diff = 4 horas > 2 min → AGREGAR

Salida: [08:00, 12:00, 13:00, 17:00]
```

**Paso 2: Emparejar**
```
Igual que Ejemplo 1 - Almuerzo válido detectado
```

**Resultado:**
```json
{
  "check_in": "2026-03-15 08:00:00",
  "check_out": "2026-03-15 17:00:00",
  "has_lunch": true,
  "lunch_duration": 1.0
}
```

---

### Ejemplo 4: Asistencia Abierta (Solo 1 Punch)

**Escenario:** Empleado llega pero no registra salida

**Punches del dispositivo:**
```
Punch 1: 2026-03-15 09:15:00 (Entrada)
```

**Resultado:**
```json
{
  "check_in": "2026-03-15 09:15:00",
  "check_out": null,
  "has_lunch": false,
  "lunch_duration": 0.0
}
```

**Nota:** Se crea asistencia abierta en hr.attendance

---

### Ejemplo 5: Almuerzo Inválido (> 4 horas)

**Escenario:** Empleado sale muy temprano al almuerzo o tiene una emergencia

**Punches del dispositivo:**
```
Punch 1: 2026-03-15 08:00:00 (Entrada)
Punch 2: 2026-03-15 11:00:00 (Sale muy temprano)
Punch 3: 2026-03-15 16:00:00 (Regresa muy tarde)
Punch 4: 2026-03-15 17:00:00 (Salida)
```

**Paso 2: Emparejar**
```
- Cantidad: 4
- lunch_start = 11:00
- lunch_end = 16:00
- lunch_duration = 16:00 - 11:00 = 5 horas

Validación: 5 horas > 4 horas → INVÁLIDO
- Usar primer y último punch
- Deducir 1 hora por defecto
```

**Resultado:**
```json
{
  "check_in": "2026-03-15 08:00:00",
  "check_out": "2026-03-15 17:00:00",
  "has_lunch": false,
  "lunch_duration": 1.0
}
```

---

### Ejemplo 6: Turno Nocturno

**Escenario:** Empleado trabaja turno nocturno

**Punches del dispositivo:**
```
Punch 1: 2026-03-15 22:00:00 (Entrada)
Punch 2: 2026-03-16 02:00:00 (Almuerzo salida)
Punch 3: 2026-03-16 03:00:00 (Almuerzo entrada)
Punch 4: 2026-03-16 06:00:00 (Salida)
```

**Resultado:**
```json
{
  "check_in": "2026-03-15 22:00:00",
  "check_out": "2026-03-16 06:00:00",
  "has_lunch": true,
  "lunch_duration": 1.0
}
```

**Cálculo de horas:**
```
Total: 06:00 (día 16) - 22:00 (día 15) = 8 horas
Deducir: 1 hora de almuerzo
Horas trabajadas: 8 - 1 = 7 horas
```

---

### Ejemplo 7: Almuerzo Corto (< 10 minutos)

**Escenario:** Empleado sale brevemente por emergencia

**Punches del dispositivo:**
```
Punch 1: 2026-03-15 08:00:00 (Entrada)
Punch 2: 2026-03-15 12:00:00 (Salida)
Punch 3: 2026-03-15 12:05:00 (Regresa - solo 5 min)
Punch 4: 2026-03-15 17:00:00 (Salida)
```

**Paso 2: Emparejar**
```
- Cantidad: 4
- lunch_start = 12:00
- lunch_end = 12:05
- lunch_duration = 12:05 - 12:00 = 5 minutos

Validación: 5 min < 10 min → INVÁLIDO
- Usar primer y último punch
- Deducir 1 hora por defecto
```

**Resultado:**
```json
{
  "check_in": "2026-03-15 08:00:00",
  "check_out": "2026-03-15 17:00:00",
  "has_lunch": false,
  "lunch_duration": 1.0
}
```

---

## 5. Resumen de Casos de Emparejamiento

| # | Punches | Almuerzo | check_in | check_out | lunch_duration | has_lunch |
|---|---------|----------|----------|-----------|----------------|-----------|
| 1 | [08:00] | N/A | 08:00 | null | 0.0 | false |
| 2 | [08:00, 17:00] | No | 08:00 | 17:00 | 1.0 | false |
| 3 | [08:00, 12:00, 13:00] | Inválido | 08:00 | 13:00 | 1.0 | false |
| 4 | [08:00, 12:00, 13:00, 17:00] | 1 hora | 08:00 | 17:00 | 1.0 | true |
| 5 | [08:00, 11:00, 16:00, 17:00] | 5h (inválido) | 08:00 | 17:00 | 1.0 | false |
| 6 | [22:00, 02:00, 03:00, 06:00] | 1 hora | 22:00 | 06:00+1d | 1.0 | true |
| 7 | [08:00, 12:00, 12:05, 17:00] | 5min (inválido) | 08:00 | 17:00 | 1.0 | false |

---

## 6. Descarga de Asistencias (download_attendance)

```
FUNCIÓN download_attendance(silent=False)
    INICIO
        // 1. Verificar conexión
        SI NO check_connection() ENTONCES
            RETORNAR Error
        
        // 2. Obtener datos del dispositivo
        attendance = conn.get_attendance()
        
        // 3. Mapear empleados
        emp_dict = {device_id: emp_id}
        
        // 4. Normalizar registros (zona horaria)
        normalized_records = []
        punches_by_emp_date = {}
        
        PARA CADA registro EN attendance:
            // Convertir a UTC
            utc_dt = convertir_a_utc(registro.timestamp)
            
            normalized_records.agregar({
                "emp_id": emp_dict[registro.user_id],
                "datetime": utc_dt,
                "punch_date": utc_dt.date()
            })
            
            // Agrupar por empleado y fecha
            key = (emp_id, punch_date)
            punches_by_emp_date[key].agregar(utc_dt)
        
        // 5. Crear registros ZK
        PARA CADA registro EN normalized_records:
            crear_en_tabla_zk(registro)
        
        // 6. Procesar pares
        PARA CADA (emp_id, punch_date), punches_list EN punches_by_emp_date:
            paired = TimePairingEngine(punches_list).pair()
            crear_o_actualizar_asistencia(paired)
        
        RETORNAR resultado
    FIN
```

---

## 7. Cálculo de Horas Trabajadas

```
horas_trabajadas = (check_out - check_in) - duracion_almuerzo

Ejemplo:
  check_in: 08:00
  check_out: 17:00
  almuerzo: 1.0 hora
  
  Total: 9 horas - 1 hora = 8 horas trabajadas
```

---

## 8. Zonas Horarias

| Componente | Zona Horaria |
|------------|-------------|
| Dispositivo ZK | Configurable (user.tz) |
| Fallback | America/Santo_Domingo |
| Odoo DB | UTC |

---

## 9. Notas Importantes

1. **Duplicados**: Punes dentro de 2 minutos se consideran duplicados
2. **Almuerzo**: Se deduce 1 hora por defecto si no se detecta válida
3. **Validación almuerzo**: Debe ser > 10 minutos y < 4 horas
4. **Asistencias abiertas**: Si hay 1 punch, se crea sin check_out
5. **Zona horaria**: Se usa la del usuario Odoo o America/Santo_Domingo

---

## Archivos Relacionados

- `zk_machine.py` - download_attendance()
- `attendance_pairing_engine.py` - TimePairingEngine
- `hr.attendance` - Modelo de asistencia
