"""Local fallback for the legacy patient-report Lambda worker."""

import csv
import json
import logging
import os
import re
import smtplib
import ssl
import zipfile
from collections.abc import Iterable
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import httpx

from settings import load_settings

logger = logging.getLogger(__name__)
def _legacy_environment() -> dict[str, str]:
    configured = os.getenv("LEGACY_DASHBOARD_CONFIG_PATH", "").strip()
    if not configured:
        raise RuntimeError("LEGACY_DASHBOARD_CONFIG_PATH is not configured")
    document = json.loads(Path(configured).read_text(encoding="utf-8"))
    stage_name = os.getenv("LEGACY_DASHBOARD_STAGE", "dev").strip()
    stage = document.get("stages", {}).get(stage_name, {})
    values = stage.get("environment_variables", {})
    if not isinstance(values, dict):
        raise RuntimeError("Legacy dashboard environment is invalid")
    return {str(key): str(value) for key, value in values.items() if value is not None}


class LegacyElasticsearch:
    def __init__(self) -> None:
        settings = load_settings()
        environment = settings.environment
        self.client = httpx.Client(
            base_url=settings.elasticsearch_url,
            auth=httpx.BasicAuth(environment.ES_USERNAME_DEFAULT, environment.ES_PASSWORD_DEFAULT.get_secret_value()),
            verify=os.getenv("DASHBOARD_ES_VERIFY_TLS", "true").casefold() not in {"0", "false", "no"},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self.environment_name = environment.THIS_ENV

    def index(self, suffix: str) -> str:
        return f"{self.environment_name}_{suffix}"

    def scan(self, index: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        response = self.client.post(f"/{index}/_search", params={"scroll": "5m", "size": "1000"}, json=body)
        response.raise_for_status()
        page = response.json()
        scroll_id = page.get("_scroll_id")
        records: list[dict[str, Any]] = []
        try:
            while True:
                hits = page.get("hits", {}).get("hits", [])
                if not hits:
                    break
                records.extend(hit for hit in hits if isinstance(hit, dict))
                if not scroll_id:
                    break
                response = self.client.post("/_search/scroll", json={"scroll": "5m", "scroll_id": scroll_id})
                response.raise_for_status()
                page = response.json()
                scroll_id = page.get("_scroll_id", scroll_id)
        finally:
            if scroll_id:
                try:
                    self.client.request("DELETE", "/_search/scroll", json={"scroll_id": [scroll_id]})
                except httpx.HTTPError:
                    logger.warning("Could not clear the report Elasticsearch scroll")
        return records


def _chunks(values: list[str], size: int = 1000) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _source(hit: dict[str, Any]) -> dict[str, Any]:
    value = hit.get("_source")
    return value if isinstance(value, dict) else {}


def _mapping(es: LegacyElasticsearch, index: str, field: str, ids: list[str], fields: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(ids):
        for hit in es.scan(index, {"query": {"terms": {field: chunk}}, "_source": fields}):
            source = _source(hit)
            key = source.get(fields[0])
            if isinstance(key, str):
                result[key] = source
    return result


def _history(es: LegacyElasticsearch, patient_ids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for chunk in _chunks(patient_ids):
        body = {"query": {"bool": {"must": [{"terms": {"patient_unique_id.keyword": chunk}}, {"match_phrase": {"info_type_key": "history"}}]}}, "_source": ["patient_unique_id", "notes"], "sort": [{"date_created": "desc"}]}
        for hit in es.scan(es.index("phr"), body):
            source = _source(hit)
            patient_id = source.get("patient_unique_id")
            notes = source.get("notes")
            if isinstance(patient_id, str) and patient_id not in result:
                result[patient_id] = notes if isinstance(notes, str) else "NA"
    return result


def _ai_analysis(es: LegacyElasticsearch, patient_ids: list[str]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for chunk in _chunks(patient_ids):
        body = {"query": {"bool": {"must": [{"terms": {"patient_unique_id.keyword": chunk}}, {"match_phrase": {"info_type_key": "ai_analysis~heart"}}]}}, "_source": ["patient_unique_id", "form_data", "date_created"], "sort": [{"date_created": "desc"}]}
        for hit in es.scan(es.index("phr"), body):
            source = _source(hit)
            patient_id = source.get("patient_unique_id")
            forms = source.get("form_data")
            created = source.get("date_created")
            if not isinstance(patient_id, str) or not isinstance(forms, list) or not forms or not isinstance(forms[0], dict):
                continue
            analysis = forms[0].get("ai_analysis")
            if isinstance(analysis, str):
                result.setdefault(patient_id, []).append({"analysis": analysis, "date": str(created or "")})
    return result


def _age(value: object) -> int | str:
    if not isinstance(value, str) or value == "1900-01-01":
        return "NA"
    try:
        born = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return "NA"
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _parse_history(notes: str) -> dict[str, str | None]:
    parsed: dict[str, str | None] = {}
    for line in notes.replace("\\n", "\n").splitlines():
        match = re.match(r"^\s*\d+\.\s*([^:]+):\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1).strip().lower().rstrip("?!.,;:")
        value = match.group(2).strip()
        parsed[key] = None if not value or value.upper() == "NA" else value
    return parsed


def _contact(source: dict[str, Any], field: str) -> str:
    values = source.get(field)
    if isinstance(values, list) and values and isinstance(values[0], dict):
        value = values[0].get("value")
        if isinstance(value, str):
            return value
    return "NA"


def generate_and_email_summary(
    organization_ids: list[str], email: str, date_from: date, date_to: date
) -> int:
    # The legacy report worker exports every active patient for the selected
    # organizations. The dates are dashboard context, not a patient-created
    # filter; applying them here made established organizations produce 503s.
    del date_from, date_to
    csv_path: Path | None = None
    zip_path: Path | None = None
    try:
        es = LegacyElasticsearch()
        patients = es.scan(es.index("patient_registration"), {"query": {"bool": {"must": [
            {"terms": {"tenant_id.keyword": organization_ids}},
            {"term": {"record_status": "active"}},
        ]}}})
        sources = [_source(hit) for hit in patients]
        patient_ids = sorted({value for source in sources if isinstance((value := source.get("unique_id")), str)})
        tenant_ids = sorted({value for source in sources if isinstance((value := source.get("tenant_id")), str)})
        doctor_ids = sorted({value for source in sources if isinstance((value := source.get("created_by")), str)})
        tenants = _mapping(es, es.index("tenant"), "unique_id.keyword", tenant_ids, ["unique_id", "name"])
        doctors = _mapping(es, es.index("provider_registration"), "login.keyword", doctor_ids, ["login", "name"])
        histories = _history(es, patient_ids)
        analyses = _ai_analysis(es, patient_ids)
        rows: list[dict[str, object]] = []
        for source in sources:
            patient_id = str(source.get("unique_id", ""))
            tenant = tenants.get(str(source.get("tenant_id", "")), {})
            doctor = doctors.get(str(source.get("created_by", "")), {})
            dob = source.get("date_of_birth")
            base: dict[str, object] = {
                "tenant_name": tenant.get("name", "NA"),
                "patient_name": " ".join(
                    part.strip() for part in (str(source.get("first_name") or ""), str(source.get("last_name") or "")) if part.strip()
                ) or "NA",
                "gender": source.get("gender"),
                "date_of_birth": dob if dob != "1900-01-01" else "NA", "age": _age(dob),
                "aih_id": source.get("file_number"), "phone": _contact(source, "phone"),
                "email": _contact(source, "email"), "created_by": source.get("created_by"),
                "doctor_name": doctor.get("name", "NA"),
            }
            history = _parse_history(histories.get(patient_id, "NA"))
            patient_analyses = analyses.get(patient_id, [])
            if patient_analyses:
                for analysis in patient_analyses:
                    rows.append({**base, "date_created": analysis["date"], "ai_analysis": analysis["analysis"], **history})
            else:
                rows.append({**base, "date_created": source.get("date_created"), "ai_analysis": "NA", **history})
        default_headers = [
            "tenant_name", "patient_name", "gender", "date_of_birth", "age",
            "aih_id", "phone", "email", "created_by", "doctor_name",
            "date_created", "ai_analysis",
        ]
        headers = list(dict.fromkeys(key for row in rows for key in row)) if rows else default_headers
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with NamedTemporaryFile("w", newline="", encoding="utf-8", suffix=".csv", prefix="patient_report_", delete=False) as output:
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
            csv_path = Path(output.name)
        with NamedTemporaryFile(suffix=".zip", prefix="patient_report_", delete=False) as archive:
            zip_path = Path(archive.name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(csv_path, arcname=f"patient_report_{timestamp}.csv")
        _send_email(email, zip_path, _legacy_environment(), timestamp)
        return len(rows)
    except Exception:
        logger.exception("Local summary report generation failed")
        raise
    finally:
        if csv_path is not None:
            csv_path.unlink(missing_ok=True)
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)


def _send_email(email: str, path: Path, environment: dict[str, str], timestamp: str) -> None:
    port = int(environment.get("SMTP_PORT") or environment.get("PORT") or "587")
    server_name = environment.get("SMTP_SERVER", "")
    username = environment.get("USERNAME", "")
    password = environment.get("PASSWORD", "")
    if not server_name or not username or not password:
        raise RuntimeError("Legacy SMTP configuration is incomplete")
    message = EmailMessage()
    message["Subject"] = "Patient Report"
    message["From"] = "noreply@aisteth.com"
    message["To"] = email
    message.set_content("Please find attached the downloadable Aisteth report")
    message.add_attachment(path.read_bytes(), maintype="application", subtype="zip", filename=f"patient_report_{timestamp}.zip")
    if port == 465:
        with smtplib.SMTP_SSL(server_name, port, context=ssl.create_default_context(), timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(server_name, port, timeout=30) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(username, password)
            smtp.send_message(message)
