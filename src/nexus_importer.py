from __future__ import annotations

import hashlib
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from . import db


COLUMN_MAP = {
    "colegio_codigo": "CODMOD I.E.",
    "colegio_nombre": "NOMBRE DE LA INSTITUCION EDUCATIVA",
    "nivel_educativo": "NIVEL EDUCATIVO",
    "cargo": "CARGO",
    "especialidad": "ESPECIALIDAD",
    "dni": "DOCUMENTO DE IDENTIDAD",
    "primer_apellido": "APELLIDO PATERNO",
    "segundo_apellido": "APELLIDO MATERNO",
    "nombre": "NOMBRES",
    "email": "EMAIL",
    "celular": "CELULAR",
    "estado": "ESTADO",
    "situacion_laboral": "SITUACION LABORAL",
}

HASH_FIELDS = [
    "dni",
    "nombre",
    "primer_apellido",
    "segundo_apellido",
    "email",
    "celular",
    "nivel_educativo",
    "cargo",
    "especialidad",
    "colegio_nombre",
    "colegio_codigo",
]


def read_upload_bytes(uploaded_file: BinaryIO | bytes) -> bytes:
    if isinstance(uploaded_file, bytes):
        return uploaded_file
    return uploaded_file.getvalue()


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_phone(value) -> str:
    text = normalize_text(value)
    return re.sub(r"\D+", "", text)


def normalize_dni(value) -> str:
    text = normalize_phone(value)
    return text.zfill(8) if text and len(text) < 8 else text


def row_hash(row: dict) -> str:
    payload = "|".join(row.get(field, "") for field in HASH_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_columns(frame: pd.DataFrame) -> None:
    missing = [
        source for source in COLUMN_MAP.values() if source not in frame.columns
    ]
    if missing:
        raise ValueError(
            "Faltan columnas requeridas en Nexus: " + ", ".join(sorted(missing))
        )


def is_active(row: pd.Series, active_estado_values: set[str] | None = None) -> bool:
    if active_estado_values:
        estado = normalize_text(row.get(COLUMN_MAP["estado"], "")).upper()
        return estado in active_estado_values

    estado = normalize_text(row.get(COLUMN_MAP["estado"], "")).upper()
    situacion = normalize_text(row.get(COLUMN_MAP["situacion_laboral"], "")).upper()
    inactive_markers = ("INACTIVO", "CESADO", "RETIRADO", "BAJA")
    return not any(marker in estado or marker in situacion for marker in inactive_markers)


def normalize_frame(
    frame: pd.DataFrame, active_estado_values: set[str] | None = None
) -> list[dict]:
    validate_columns(frame)
    rows: list[dict] = []
    for _, source in frame.iterrows():
        if not is_active(source, active_estado_values):
            continue
        row = {
            target: normalize_text(source[column])
            for target, column in COLUMN_MAP.items()
        }
        row["dni"] = normalize_dni(row["dni"])
        row["celular"] = normalize_phone(row["celular"])
        row["email"] = row["email"].lower()
        row["row_hash"] = row_hash(row)
        if row["dni"] and row["colegio_codigo"]:
            rows.append(row)
    return rows


def preview_excel(content: bytes) -> dict:
    frame = _read_excel_bytes(content)
    validate_columns(frame)
    rows = normalize_frame(frame)
    schools = {(r["colegio_codigo"], r["colegio_nombre"]) for r in rows}
    return {
        "raw_rows": len(frame),
        "active_rows": len(rows),
        "schools": len(schools),
        "columns": list(frame.columns),
    }


def import_excel(
    content: bytes,
    *,
    filename: str,
    tipo: str = "automatico",
    active_estado_values: set[str] | None = None,
) -> int:
    frame = _read_excel_bytes(content)
    normalized = normalize_frame(frame, active_estado_values)
    source_hash = file_hash(content)
    now = datetime.now().isoformat(timespec="seconds")

    with db.connect() as conn:
        db.init_db()
        version_id = db.create_version(
            conn,
            date_time=now,
            tipo=tipo,
            filename=filename,
            source_hash=source_hash,
            row_count=len(normalized),
        )
        rows = [{**row, "version_id": version_id} for row in normalized]
        db.insert_docentes(conn, rows)
    return version_id


def _read_excel_bytes(content: bytes) -> pd.DataFrame:
    # Some pandas/openpyxl versions handle BytesIO inconsistently for uploaded files
    # with spaces in names. A temp file keeps the importer predictable.
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=True) as handle:
        handle.write(content)
        handle.flush()
        return pd.read_excel(Path(handle.name), sheet_name="nexus")
