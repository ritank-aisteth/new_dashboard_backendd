"""Small typed Elasticsearch HTTP gateway for local configured dashboard reads."""

import hashlib
import hmac
from collections.abc import Generator
from datetime import date
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlencode

import httpx
from pydantic import JsonValue, TypeAdapter

from backend_dashboard.schemas import BreakdownItem, DateRange, MetricPoint, MurmurBreakdown, PatientBreakdown
from backend_dashboard.settings import DashboardSettings

JsonObject = dict[str, JsonValue]
JSON_OBJECT = TypeAdapter(JsonObject)


class ExternalServiceError(RuntimeError):
    """Raised when a configured service cannot return a valid response."""


class ElasticsearchGateway:
    def __init__(self, settings: DashboardSettings) -> None:
        environment = settings.environment
        self._environment_name = environment.THIS_ENV
        self._basic_auth = httpx.BasicAuth(environment.ES_USERNAME_DEFAULT, environment.ES_PASSWORD_DEFAULT.get_secret_value())
        self._aws_auth = AwsSigV4Auth(
            access_key=environment.ACCESS_KEY.get_secret_value(),
            secret_key=environment.SECRET_KEY.get_secret_value(),
            region=environment.DYNAMODB_REGION,
        )

        self._client = httpx.Client(
            base_url=settings.elasticsearch_url,
            timeout=httpx.Timeout(15.0, connect=5.0),
            verify=os_verify_tls(),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def index(self, suffix: str) -> str:
        return f"{self._environment_name}_{suffix}"

    def search(self, index: str, body: JsonObject) -> JsonObject:
        try:
            response = self._client.post(f"/{index}/_search", json=body, auth=self._basic_auth)
            if response.status_code in {401, 403}:
                response = self._client.post(f"/{index}/_search", json=body, auth=self._aws_auth)
            response.raise_for_status()
            return JSON_OBJECT.validate_python(response.json())
        except (httpx.HTTPError, ValueError) as error:
            raise ExternalServiceError("Elasticsearch request failed") from error

    def records(self, index: str, body: JsonObject) -> list[JsonObject]:
        response = self.search(index, body)
        hits = as_object(response.get("hits")).get("hits")
        if not isinstance(hits, list):
            return []
        records: list[JsonObject] = []
        for hit in hits:
            hit_object = as_object(hit)
            source = as_object(hit_object.get("_source"))
            if source:
                records.append(source)
        return records

    def index_document(self, index: str, document_id: str, body: JsonObject) -> None:
        try:
            response = self._client.put(f"/{index}/_doc/{quote(document_id, safe='-_.~')}", params={"refresh": "wait_for"}, json=body, auth=self._basic_auth)
            if response.status_code in {401, 403}:
                response = self._client.put(f"/{index}/_doc/{quote(document_id, safe='-_.~')}", params={"refresh": "wait_for"}, json=body, auth=self._aws_auth)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ExternalServiceError("Elasticsearch write failed") from error

    def metric(self, index: str, report_range: DateRange, filters: list[JsonObject] | None = None) -> tuple[float, list[MetricPoint]]:
        clauses: list[JsonObject] = [
            {"range": {"date_created": {"gte": report_range.date_from.isoformat(), "lte": report_range.date_to.isoformat()}}}
        ]
        clauses.extend(filters or [])
        query_filter: list[JsonValue] = list(clauses)
        body: JsonObject = {
            "size": 0,
            "track_total_hits": True,
            "query": {"bool": {"filter": query_filter}},
            "aggs": {"by_date": {"date_histogram": {"field": "date_created", "calendar_interval": "month", "min_doc_count": 0}}},
        }
        response = self.search(index, body)
        total = number_value(as_object(as_object(response.get("hits")).get("total")).get("value"))
        buckets = as_object(as_object(response.get("aggregations")).get("by_date")).get("buckets")
        points: list[MetricPoint] = []
        if isinstance(buckets, list):
            for bucket in buckets:
                item = as_object(bucket)
                raw_date = string_value(item.get("key_as_string"))
                if raw_date:
                    points.append(MetricPoint(date=parse_date(raw_date), value=number_value(item.get("doc_count"))))
        return total, points

    def patient_breakdown(self, report_range: DateRange, tenant_id: str | None = None) -> PatientBreakdown:
        filters: list[JsonObject] = [
            {"range": {"date_created": {"gte": report_range.date_from.isoformat(), "lte": report_range.date_to.isoformat()}}},
            {"term": {"record_status.keyword": "active"}},
        ]
        if tenant_id:
            filters.append({"term": {"tenant_id.keyword": tenant_id}})
        query_filter: list[JsonValue] = list(filters)
        rows = self.records(
            self.index("patient_registration"),
            {"size": 10000, "_source": ["gender", "date_of_birth"], "query": {"bool": {"filter": query_filter}}},
        )
        total = len(rows)
        quick = 0
        genders = {"Male": 0, "Female": 0, "Others": 0, "Anonymous": 0}
        ages = {"Child (0-12)": 0, "Adolescent (13-19)": 0, "Young Adult (20-35)": 0, "Adult (36-65)": 0, "Late Adult (66+)": 0, "Anonymous (Undisclosed Age)": 0}
        for row in rows:
            gender = string_value(row.get("gender")).strip().casefold()
            if gender == "male": genders["Male"] += 1
            elif gender == "female": genders["Female"] += 1
            elif gender in {"", "na", "n/a", "none", "anonymous", "unknown"}: genders["Anonymous"] += 1
            else: genders["Others"] += 1
            dob = string_value(row.get("date_of_birth")).strip()
            if not dob or dob.startswith("1900-01-01"):
                quick += 1
                ages["Anonymous (Undisclosed Age)"] += 1
                continue
            try:
                born = date.fromisoformat(dob[:10])
                age = report_range.date_to.year - born.year - ((report_range.date_to.month, report_range.date_to.day) < (born.month, born.day))
            except ValueError:
                ages["Anonymous (Undisclosed Age)"] += 1
                continue
            if age <= 12: ages["Child (0-12)"] += 1
            elif age <= 19: ages["Adolescent (13-19)"] += 1
            elif age <= 35: ages["Young Adult (20-35)"] += 1
            elif age <= 65: ages["Adult (36-65)"] += 1
            else: ages["Late Adult (66+)"] += 1

        def items(values: dict[str, int]) -> list[BreakdownItem]:
            return [BreakdownItem(label=label, count=count, percentage=round((count / total * 100) if total else 0, 1)) for label, count in values.items()]

        return PatientBreakdown(
            total=total,
            auscultation_type=items({"Quick Auscultation Patients": quick, "Registered Patients": total - quick}),
            gender_distribution=items(genders),
            age_group_distribution=items(ages),
        )

    def murmur_breakdown(self, report_range: DateRange, tenant_id: str | None = None) -> MurmurBreakdown:
        murmur_values: list[JsonValue] = ["Murmur", "Murmur ", "Murmur, background is very noisy.", "Murmur.", "Murmur. "]
        filters: list[JsonObject] = [
            {"terms": {"form_data.ai_analysis.keyword": murmur_values}},
            {"range": {"date_created": {"gte": report_range.date_from.isoformat(), "lte": report_range.date_to.isoformat()}}},
        ]
        if tenant_id:
            filters.append({"term": {"tenant_id.keyword": tenant_id}})
        murmur_rows = self.records(
            self.index("phr"),
            {"size": 10000, "_source": ["patient_unique_id"], "query": {"bool": {"filter": list(filters)}}},
        )
        patient_ids = sorted({string_value(row.get("patient_unique_id")) for row in murmur_rows if string_value(row.get("patient_unique_id"))})
        patient_rows: list[JsonObject] = []
        for offset in range(0, len(patient_ids), 1000):
            batch: list[JsonValue] = []
            batch.extend(patient_ids[offset : offset + 1000])
            patient_rows.extend(self.records(
                self.index("patient_registration"),
                {"size": 1000, "_source": ["gender", "date_of_birth"], "query": {"bool": {"filter": [{"terms": {"unique_id.keyword": batch}}]}}},
            ))
        total = len(murmur_rows)
        genders = {"Male": 0, "Female": 0, "Others": 0, "Anonymous": 0}
        ages = {"Child (0-12)": 0, "Adolescent (13-19)": 0, "Young Adult (20-35)": 0, "Adult (36-65)": 0, "Late Adult (66+)": 0, "Anonymous (Undisclosed Age)": 0}
        for row in patient_rows:
            gender = string_value(row.get("gender")).strip().casefold()
            if gender == "male": genders["Male"] += 1
            elif gender == "female": genders["Female"] += 1
            elif gender in {"other", "others"}: genders["Others"] += 1
            else: genders["Anonymous"] += 1
            dob = string_value(row.get("date_of_birth")).strip()
            if not dob or dob.startswith("1900-01-01"):
                ages["Anonymous (Undisclosed Age)"] += 1
                continue
            try:
                born = date.fromisoformat(dob[:10])
                age = report_range.date_to.year - born.year - ((report_range.date_to.month, report_range.date_to.day) < (born.month, born.day))
            except ValueError:
                ages["Anonymous (Undisclosed Age)"] += 1
                continue
            if age <= 12: ages["Child (0-12)"] += 1
            elif age <= 19: ages["Adolescent (13-19)"] += 1
            elif age <= 35: ages["Young Adult (20-35)"] += 1
            elif age <= 65: ages["Adult (36-65)"] += 1
            else: ages["Late Adult (66+)"] += 1
        unmatched = max(total - len(patient_rows), 0)
        genders["Anonymous"] += unmatched
        ages["Anonymous (Undisclosed Age)"] += unmatched

        def items(values: dict[str, int]) -> list[BreakdownItem]:
            return [BreakdownItem(label=label, count=count, percentage=round((count / total * 100) if total else 0, 1)) for label, count in values.items()]

        return MurmurBreakdown(total_reports=total, gender_distribution=items(genders), age_group_distribution=items(ages))

    def clinical_analysis_breakdowns(self, report_range: DateRange, tenant_id: str | None = None) -> tuple[list[BreakdownItem], list[BreakdownItem]]:
        date_filter: JsonObject = {"range": {"date_created": {"gte": report_range.date_from.isoformat(), "lte": report_range.date_to.isoformat()}}}
        tenant_filter: list[JsonObject] = [{"term": {"tenant_id.keyword": tenant_id}}] if tenant_id else []
        normal_values: list[JsonValue] = ["Normal", "Normal ", "normal", "Normal, no murmur detected.", "Normal, no murmur detected. ", "Normal, but noisy background", "Normal, but noisy background "]
        murmur_values: list[JsonValue] = ["Murmur", "Murmur ", "Murmur, background is very noisy.", "Murmur.", "Murmur. "]
        heart_filters: list[JsonObject] = [{"prefix": {"info_type_key.keyword": "ai_analysis~heart"}}, date_filter, *tenant_filter]
        heart_rows = self.records(self.index("phr"), {"size": 10000, "_source": ["form_data.ai_analysis"], "query": {"bool": {"filter": list(heart_filters)}}})
        heart = {"Normal": 0, "Murmur": 0, "Other / inconclusive": 0}
        normal_set = {str(value).casefold() for value in normal_values}
        murmur_set = {str(value).casefold() for value in murmur_values}
        for row in heart_rows:
            value = nested_analysis_value(row).casefold()
            if value in normal_set: heart["Normal"] += 1
            elif value in murmur_set: heart["Murmur"] += 1
            else: heart["Other / inconclusive"] += 1

        lung_filters: list[JsonObject] = [{"prefix": {"info_type_key.keyword": "ai_analysis~lungs"}}, date_filter, *tenant_filter]
        lung_rows = self.records(self.index("phr"), {"size": 10000, "_source": ["form_data.ai_analysis"], "query": {"bool": {"filter": list(lung_filters)}}})
        lung = {"Adventitious sounds present": 0, "Adventitious sounds absent": 0, "Other / inconclusive": 0}
        for row in lung_rows:
            value = nested_analysis_value(row).casefold()
            if value == "adventitious sounds present.": lung["Adventitious sounds present"] += 1
            elif value == "adventitious sounds absent.": lung["Adventitious sounds absent"] += 1
            else: lung["Other / inconclusive"] += 1

        def items(values: dict[str, int]) -> list[BreakdownItem]:
            total = sum(values.values())
            return [BreakdownItem(label=label, count=count, percentage=round((count / total * 100) if total else 0, 1)) for label, count in values.items()]

        return items(heart), items(lung)


class AwsSigV4Auth(httpx.Auth):
    """Signs buffered HTTP requests for an AWS-managed Elasticsearch domain."""

    requires_request_body = True

    def __init__(self, access_key: str, secret_key: str, region: str) -> None:
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(request.content).hexdigest()
        host = request.url.host
        if request.url.port is not None and request.url.port not in {80, 443}:
            host = f"{host}:{request.url.port}"
        canonical_uri = quote(request.url.path or "/", safe="/-_.~")
        pairs = sorted(parse_qsl(request.url.query.decode("ascii"), keep_blank_values=True))
        canonical_query = urlencode(pairs, quote_via=quote, safe="-_.~")
        canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join((request.method, canonical_uri, canonical_query, canonical_headers, signed_headers, payload_hash))
        scope = f"{date_stamp}/{self._region}/es/aws4_request"
        string_to_sign = "\n".join(("AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()))
        signing_key = self._signing_key(date_stamp)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        request.headers["Host"] = host
        request.headers["X-Amz-Date"] = amz_date
        request.headers["X-Amz-Content-Sha256"] = payload_hash
        request.headers["Authorization"] = f"AWS4-HMAC-SHA256 Credential={self._access_key}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
        yield request

    def _signing_key(self, date_stamp: str) -> bytes:
        date_key = hmac.new(f"AWS4{self._secret_key}".encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
        region_key = hmac.new(date_key, self._region.encode("utf-8"), hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"es", hashlib.sha256).digest()
        return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()

def os_verify_tls() -> bool:
    import os

    return os.getenv("DASHBOARD_ES_VERIFY_TLS", "true").casefold() not in {"0", "false", "no"}


def as_object(value: JsonValue | None) -> JsonObject:
    if isinstance(value, dict):
        return value
    return {}


def string_value(value: JsonValue | None, default: str = "") -> str:
    return value if isinstance(value, str) else default


def number_value(value: JsonValue | None) -> float:
    if isinstance(value, bool):
        return 0.0
    return float(value) if isinstance(value, (int, float)) else 0.0


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return date.today()


def nested_analysis_value(row: JsonObject) -> str:
    form_data = row.get("form_data")
    if isinstance(form_data, list):
        for item in form_data:
            value = as_object(item).get("ai_analysis")
            if isinstance(value, str):
                return value.strip()
    if isinstance(form_data, dict):
        value = form_data.get("ai_analysis")
        return value.strip() if isinstance(value, str) else ""
    return ""
