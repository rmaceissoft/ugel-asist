# Plan de Ejecucion

## Objetivo

Construir una aplicacion web en Streamlit para cargar archivos Excel de Nexus, guardar cada carga como una nueva version en SQLite, detectar colegios con cambios en su personal docente y generar plantillas Excel de control de asistencia pre-pobladas para esos colegios.

## Contexto Validado

- Archivo Nexus de referencia: `assets/nexus 2026-06 (OK).xlsx`
- Hoja Nexus detectada: `nexus`
- Plantilla base: `assets/UGEL - Plantilla de asistencia.xlsx`
- Hojas de la plantilla:
  - `ANEXO 3`: reporte de asistencia detallado
  - `ANEXO 4`: reporte consolidado de inasistencias, tardanzas y permisos
- Stack requerido:
  - Python
  - Streamlit
  - SQLite3

## Cambios Incorporados Desde `REQUIREMENTS.md`

- Se agrega un modelo de datos explicito:
  - `Version`
  - `Docentes`
- Cada carga de Nexus debe guardarse como una version nueva.
- `Version.tipo` se guarda con valor por defecto `automatico`; no se mostrara en el formulario de carga.
- La tabla principal de docentes debe almacenar los campos definidos en requisitos:
  - DNI
  - nombre
  - primer apellido
  - segundo apellido
  - email
  - celular
  - nivel educativo
  - cargo
  - nombre de colegio
  - codigo de colegio
- El flujo principal queda centrado en descargar los Excel de colegios con cambios respecto a la version anterior.

## Supuestos Funcionales

- El codigo de colegio se mapeara inicialmente desde `CODMOD I.E.` del Nexus.
- El nombre de colegio se mapeara desde `NOMBRE DE LA INSTITUCION EDUCATIVA`.
- `Apellido 1` se mapeara desde `APELLIDO PATERNO`.
- `Apellido 2` se mapeara desde `APELLIDO MATERNO`.
- `DNI` se mapeara desde `DOCUMENTO DE IDENTIDAD`.
- `nombre` se mapeara desde `NOMBRES`.
- `nivel_educativo` se mapeara desde `NIVEL EDUCATIVO`.
- `cargo` se mapeara desde `CARGO`.
- `email` se mapeara desde `EMAIL`.
- `celular` se mapeara desde `CELULAR`.
- La columna incompleta `e.` en `REQUIREMENTS.md` sigue pendiente de confirmacion. Mientras tanto, se considera necesario guardar `email`, `celular`, `nivel_educativo`, `cargo`, `colegio_nombre` y `colegio_codigo` porque aparecen en el modelo de datos nuevo o son necesarios para la plantilla.
- "Personal activo" requiere confirmacion funcional. Como implementacion inicial, se filtrara usando una regla configurable basada en `ESTADO` y, si hace falta, `SITUACION LABORAL`.
- Para detectar cambios, se comparara el conjunto de docentes de cada colegio entre la nueva version y la version anterior usando `dni` como identificador principal.

## Arquitectura Propuesta

### Estructura de proyecto

```text
.
|-- app.py
|-- pyproject.toml
|-- uv.lock
|-- data/
|   `-- ugel.sqlite3
|-- src/
|   |-- db.py
|   |-- nexus_importer.py
|   |-- change_detector.py
|   |-- attendance_template.py
|   `-- excel_utils.py
`-- assets/
    |-- nexus 2026-06 (OK).xlsx
    `-- UGEL - Plantilla de asistencia.xlsx
```

### Dependencias

El proyecto usara `uv` como gestor de paquetes y entorno virtual.

- `streamlit`: interfaz web.
- `pandas`: lectura, normalizacion y comparacion tabular.
- `openpyxl`: lectura y escritura de `.xlsx` conservando formato de plantilla.

Comandos esperados:

```bash
uv sync
uv run streamlit run app.py
```

## Modelo de Datos SQLite

### `versions`

Representa cada carga del Excel de Nexus.

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `date_time TEXT NOT NULL`
- `tipo TEXT NOT NULL DEFAULT 'automatico'`
- `filename TEXT`
- `source_hash TEXT`
- `row_count INTEGER NOT NULL DEFAULT 0`

Validaciones:

- `tipo` se guarda como `automatico` en las cargas realizadas desde la interfaz.
- `source_hash` permite detectar cargas duplicadas del mismo archivo.

### `docentes`

Representa el snapshot normalizado de docentes por version.

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `version_id INTEGER NOT NULL`
- `dni TEXT NOT NULL`
- `nombre TEXT`
- `primer_apellido TEXT`
- `segundo_apellido TEXT`
- `email TEXT`
- `celular TEXT`
- `nivel_educativo TEXT`
- `cargo TEXT`
- `colegio_nombre TEXT`
- `colegio_codigo TEXT NOT NULL`
- `row_hash TEXT NOT NULL`

Indices recomendados:

- `idx_docentes_version` sobre `version_id`
- `idx_docentes_version_colegio` sobre `version_id, colegio_codigo`
- `idx_docentes_version_dni` sobre `version_id, dni`

### `school_changes`

Tabla derivada para guardar el resultado de comparacion entre versiones.

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `version_id INTEGER NOT NULL`
- `colegio_codigo TEXT NOT NULL`
- `colegio_nombre TEXT`
- `added_count INTEGER NOT NULL DEFAULT 0`
- `removed_count INTEGER NOT NULL DEFAULT 0`
- `modified_count INTEGER NOT NULL DEFAULT 0`
- `has_changes INTEGER NOT NULL DEFAULT 0`
- `change_summary_json TEXT`

## Mapeo de Columnas Nexus

| Campo interno | Columna Nexus |
| --- | --- |
| `colegio_codigo` | `CODMOD I.E.` |
| `colegio_nombre` | `NOMBRE DE LA INSTITUCION EDUCATIVA` |
| `nivel_educativo` | `NIVEL EDUCATIVO` |
| `cargo` | `CARGO` |
| `dni` | `DOCUMENTO DE IDENTIDAD` |
| `primer_apellido` | `APELLIDO PATERNO` |
| `segundo_apellido` | `APELLIDO MATERNO` |
| `nombre` | `NOMBRES` |
| `email` | `EMAIL` |
| `celular` | `CELULAR` |
| `especialidad` para plantilla | `ESPECIALIDAD` |

Nota: aunque `especialidad` no aparece en el nuevo modelo `Docentes`, debe conservarse durante la importacion o incorporarse al modelo si se requiere llenar la columna `Especialidad` de la plantilla Excel.

## Fases de Implementacion

### 1. Inicializacion del proyecto

- Crear `pyproject.toml` con las dependencias de runtime.
- Usar `uv lock` / `uv sync` para generar y sincronizar `uv.lock`.
- Crear estructura `src/` y `data/`.
- Implementar inicializacion idempotente de SQLite en `src/db.py`.
- Crear funciones para obtener la ultima version y la version anterior.

### 2. Importador de Nexus

- Leer Excel con `pandas.read_excel`.
- Validar que existan las columnas requeridas para `Docentes`.
- Normalizar codigos leidos como numero, por ejemplo valores terminados en `.0`.
- Normalizar DNI, nombres, apellidos, email y celular.
- Filtrar personal activo con la regla definida.
- Crear registro en `versions`.
- Insertar docentes normalizados asociados a `version_id`.
- Calcular `row_hash` con los campos relevantes para detectar modificaciones.

### 3. Deteccion de cambios por colegio

- Comparar la nueva version contra la version anterior inmediata.
- Agrupar docentes por `colegio_codigo`.
- Detectar:
  - Altas: DNI existe en nueva version y no en anterior.
  - Bajas: DNI existe en anterior y no en nueva.
  - Modificaciones: mismo DNI con diferente `row_hash`.
- Guardar resultados en `school_changes`.
- Si no existe version anterior, mostrar la carga como primera version sin comparacion historica.

### 4. Generacion de plantillas Excel

- Abrir `assets/UGEL - Plantilla de asistencia.xlsx` con `openpyxl`.
- Para un colegio determinado:
  - Obtener docentes de la version seleccionada.
  - Poblar encabezados de colegio, nivel y periodo si corresponde.
  - Poblar `ANEXO 3` desde la fila de docentes del formato.
  - Poblar `ANEXO 4` desde la fila de docentes del formato.
  - Mantener estilos, bordes, formulas y formato visual de la plantilla.
- Mapear columnas de plantilla:
  - `N°`
  - `DNI`
  - `Apellidos y Nombres`
  - `Cargo`
  - `Especialidad`
  - `N° Telefono`
  - `Correo Electronico`
- Generar archivo en memoria para descarga individual.
- Generar ZIP con todos los colegios que tengan cambios.

### 5. Interfaz Streamlit

- Pantalla de carga:
  - Subir archivo Nexus `.xlsx`.
  - Guardar la version con `tipo = automatico`.
  - Mostrar validaciones, conteo de filas y colegios detectados.
  - Guardar como nueva version.
- Pantalla de cambios:
  - Mostrar version actual y version anterior comparada.
  - Listar colegios con cambios.
  - Mostrar altas, bajas y modificaciones por colegio.
  - Permitir busqueda por codigo o nombre de colegio.
  - Descargar plantilla individual por colegio.
  - Descargar ZIP de todos los colegios con cambios.
- Pantalla de historial:
  - Listar versiones cargadas.
  - Mostrar fecha, tipo, archivo y cantidad de docentes.

### 6. Validacion Manual

Para acelerar el desarrollo inicial, no se implementaran pruebas automatizadas en esta primera pasada. La verificacion se hara con validacion manual enfocada en el flujo principal.

- Instalar dependencias con `uv sync`.
- Levantar la aplicacion con `uv run streamlit run app.py`.
- Cargar `assets/nexus 2026-06 (OK).xlsx`.
- Verificar que se crea un registro en `versions`.
- Verificar que los docentes se guardan con el `version_id` correcto.
- Cargar una segunda version modificada de prueba.
- Verificar que aparecen colegios con cambios.
- Descargar un Excel individual.
- Descargar ZIP de colegios con cambios.
- Abrir los Excel generados y comparar contra `assets/UGEL - Plantilla de asistencia.xlsx`.

## Orden de Trabajo Recomendado

1. Crear estructura base y configurar dependencias con `uv`.
2. Implementar base de datos con el modelo nuevo.
3. Implementar importador y normalizador de Nexus.
4. Implementar comparador entre versiones.
5. Implementar generador de plantilla Excel.
6. Implementar interfaz Streamlit.
7. Validar manualmente con los archivos de `assets/`.

## Riesgos y Pendientes

- Confirmar que `codigo_codigo` en `REQUIREMENTS.md` significa `colegio_codigo`.
- Confirmar la columna faltante indicada como `e.`.
- Confirmar si `especialidad` debe agregarse formalmente a `Docentes`, porque la plantilla tiene una columna para ese dato.
- Confirmar la regla exacta para determinar "personal activo".
- Confirmar si deben incluirse solo docentes o tambien directivos y auxiliares.
- Confirmar si una institucion con varios niveles debe generar una plantilla unica o una por nivel educativo.
- Confirmar como se selecciona el periodo de la plantilla.
