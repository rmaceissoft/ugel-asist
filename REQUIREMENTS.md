Sistema web para generar plantillas (excel) de control de asistencia de profesores
que esten pre-populados con el personal activo de cada colegio.

## Funcionalidades:
- Cargar un excel de Nexus ("./assets/nexus 2026-06 (OK).xlsx") que contiene el personal actualizado de todos los colegios de la UGEL.
De este excel se necesitan almacenar las siguientes columnas:
a. Especialidad
b. Apellido 1
c. Appelido 2
d. DNI
e. 

- Generar la plantilla (Excel) de asistencia para un colegio determinado. Ver los siguientes ficheros para 
referencia del formato de la plantilla a generar

## Flujo de trabajo:
1. Se carga el fichero excel de Nexus y sse guada como una version nueva
2. Se muestra un listado de los colegios que sufrieron cambios en su personal docente
3. Se descarga los excels de los colegios que sufrieron cambios respecto a la version anterior.

## Modelo de Datos:

- Version:
. id
. date_time
. tipo (automatico / manual). default=automatico

- Docentes:
. id
. dni
. nombre
. primer_apellido
. segundo_apellido
. email
. celular
. nivel_educativo
. cargo
. colegio_nombre
. codigo_codigo

## Tech Stack:
- streamlit
- database: sqlite3
- lenguage de programacion: python
