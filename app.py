from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src import db
from src.attendance_template import (
    generate_changed_schools_zip,
    generate_school_workbook,
)
from src.change_detector import calculate_and_store_changes
from src.excel_utils import excel_mime_type, zip_mime_type
from src.nexus_importer import import_excel, preview_excel, read_upload_bytes


st.set_page_config(page_title="UGEL Asistencia", layout="wide")


def main() -> None:
    db.init_db()
    st.title("Asist UGEL LUYA")
    st.subheader("Generador de plantillas de asistencia")

    tab_upload, tab_changes, tab_history = st.tabs(
        ["Carga Nexus", "Colegios con cambios", "Historial"]
    )

    with tab_upload:
        render_upload()
    with tab_changes:
        render_changes()
    with tab_history:
        render_history()


def render_upload() -> None:
    st.subheader("Nueva version")
    uploaded = st.file_uploader("Archivo Nexus (.xlsx)", type=["xlsx"])

    if not uploaded:
        st.info("Sube un archivo Nexus para previsualizar la carga.")
        return

    content = read_upload_bytes(uploaded)
    try:
        preview = preview_excel(content)
    except Exception as exc:
        st.error(f"No se pudo leer el archivo Nexus: {exc}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Filas en Nexus", preview["raw_rows"])
    col2.metric("Docentes activos", preview["active_rows"])
    col3.metric("Colegios detectados", preview["schools"])

    if st.button("Guardar como nueva version", type="primary"):
        try:
            version_id = import_excel(
                content,
                filename=uploaded.name,
                tipo="automatico",
            )
            changes = calculate_and_store_changes(version_id)
        except Exception as exc:
            st.error(f"No se pudo guardar la version: {exc}")
            return
        changed_count = sum(1 for change in changes if change["has_changes"])
        st.success(
            f"Version {version_id} guardada. Colegios con cambios: {changed_count}."
        )


def render_changes() -> None:
    with db.connect() as conn:
        versions = db.get_versions(conn)

    if not versions:
        st.info("Aun no hay versiones cargadas.")
        return

    selected = st.selectbox(
        "Version",
        options=[row["id"] for row in versions],
        format_func=lambda version_id: _version_label(versions, version_id),
    )
    query = st.text_input("Buscar por codigo o nombre de colegio").strip().upper()
    only_changed = st.toggle("Mostrar solo colegios con cambios", value=True)

    with db.connect() as conn:
        rows = db.get_changed_schools(conn, selected, only_changed=only_changed)

    if query:
        rows = [
            row
            for row in rows
            if query in row["colegio_codigo"].upper()
            or query in (row["colegio_nombre"] or "").upper()
        ]

    if not rows:
        st.info("No hay colegios para mostrar con los filtros actuales.")
        return

    frame = pd.DataFrame(
        [
            {
                "Codigo": row["colegio_codigo"],
                "Colegio": row["colegio_nombre"],
                "Altas": row["added_count"],
                "Bajas": row["removed_count"],
                "Modificaciones": row["modified_count"],
            }
            for row in rows
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)

    st.divider()
    col1, col2 = st.columns([2, 1])
    school_options = {f"{r['colegio_codigo']} - {r['colegio_nombre']}": r for r in rows}
    selected_label = col1.selectbox("Colegio para descarga individual", school_options)
    selected_school = school_options[selected_label]
    individual = generate_school_workbook(selected, selected_school["colegio_codigo"])
    col2.download_button(
        "Descargar Excel",
        data=individual,
        file_name=f"{selected_school['colegio_codigo']}.xlsx",
        mime=excel_mime_type(),
    )

    changed_rows = [row for row in rows if row["has_changes"]]
    if changed_rows:
        zip_content = generate_changed_schools_zip(selected)
        st.download_button(
            "Descargar ZIP de colegios con cambios",
            data=zip_content,
            file_name=f"plantillas_version_{selected}.zip",
            mime=zip_mime_type(),
            type="primary",
        )

    with st.expander("Detalle tecnico de cambios"):
        for row in rows:
            summary = json.loads(row["change_summary_json"] or "{}")
            st.markdown(f"**{row['colegio_codigo']} - {row['colegio_nombre']}**")
            st.json(summary)


def render_history() -> None:
    with db.connect() as conn:
        versions = db.get_versions(conn)
        totals = {row["id"]: db.count_docentes(conn, row["id"]) for row in versions}

    if not versions:
        st.info("Aun no hay versiones cargadas.")
        return

    frame = pd.DataFrame(
        [
            {
                "Version": row["id"],
                "Fecha": row["date_time"],
                "Tipo": row["tipo"],
                "Archivo": row["filename"],
                "Docentes": totals[row["id"]],
            }
            for row in versions
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)


def _version_label(versions, version_id: int) -> str:
    for row in versions:
        if row["id"] == version_id:
            return f"{row['id']} - {row['date_time']} - {row['filename']}"
    return str(version_id)


if __name__ == "__main__":
    main()
