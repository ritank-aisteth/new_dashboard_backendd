/**
 * TypeScript contracts matching `backend_dashboard.schemas`.
 *
 * Raw record interfaces may contain sensitive identifiers. Dashboard routes should
 * return the aggregate DTOs at the bottom of this file unless a reviewed workflow
 * explicitly requires record-level data.
 */

export type ISODate = string;
export type ISODateTime = string;
export type Identifier = string;
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export type RecordStatus = "active" | "inactive" | "deleted" | "pending";
export type RequestStatus = "pending" | "approved" | "rejected";
export type PipelineStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
export type FeedbackSentiment = "positive" | "negative" | "neutral";

export interface GeoPoint {
  latitude: number;
  longitude: number;
}

export interface ContactPoint {
  type?: string | null;
  value?: string | null;
  country_code?: string | null;
  is_primary?: boolean | null;
}

export interface TenantRecord {
  unique_id: Identifier;
  name: string;
  abdm_service_id?: string | null;
  city: string;
  country: string;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  location?: GeoPoint | null;
  pincode: string;
  record_status: RecordStatus;
  state: string;
  tags?: string | null;
}

export interface ProviderRegistrationRecord {
  login: Identifier;
  unique_id: Identifier;
  tenant_id: Identifier;
  tenant_name?: string | null;
  name: string;
  address?: string | null;
  created_by?: string | null;
  c_un_cre_by?: string | null;
  c_un_upd_by?: string | null;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  device_id?: string | null;
  email: ContactPoint[];
  geo_point?: GeoPoint | null;
  nickname?: string | null;
  phone: ContactPoint[];
  record_status: RecordStatus;
  record_type: string;
  role: string;
  tags?: string | null;
  updated_by?: string | null;
}

export interface PatientRegistrationRecord {
  unique_id: Identifier;
  file_number: Identifier;
  tenant_id: Identifier;
  created_by: Identifier;
  c_un_cre_by?: string | null;
  date_created: ISODateTime;
  date_of_birth?: string | null;
  date_updated: ISODateTime;
  first_name: string;
  gender: string;
  record_status: RecordStatus;
  updated_by: Identifier;
}

export interface PhrRecord {
  patient_unique_id: Identifier;
  info_type_key: Identifier;
  unique_id: Identifier;
  tenant_id: Identifier;
  created_by: Identifier;
  updated_by: Identifier;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  file_uploads: JsonObject[];
  form_data: JsonObject[];
}

export interface PhrMetadataRecord {
  patient_unique_id: Identifier;
  info_type_key: Identifier;
  unique_id: Identifier;
  tenant_id: Identifier;
  created_by: Identifier;
  login: Identifier;
  date_created: ISODateTime;
  form_data: JsonObject[];
}

export interface AistethAudioBackupRecord {
  unique_id: Identifier;
  savedas_filename: string;
  original_filename: string;
  tenant_id: Identifier;
  created_by: Identifier;
  login: Identifier;
  date_created: ISODateTime;
  date_file_created: ISODateTime;
}

export interface MlPipelineStatusRecord {
  unique_id: Identifier;
  filename: string;
  info_type_key: string;
  created_by: Identifier;
  login: Identifier;
  status: PipelineStatus;
  tenant_id: Identifier;
  ttl_timestamp?: number | null;
  date_created: ISODateTime;
}

export interface SubscriptionTransactionRecord {
  tenant_id: Identifier;
  info_type_key: Identifier;
  unique_id: Identifier;
  consumption_type: string;
  created_by: Identifier;
  c_un_cre_by?: string | null;
  c_un_upd_by?: string | null;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  description: JsonObject[];
  login: Identifier;
  points: number;
  record_status: RecordStatus;
  updated_by: Identifier;
}

export interface AistethFeedbackRecord {
  patient_unique_id: Identifier;
  info_type_key: Identifier;
  unique_id: Identifier;
  login: Identifier;
  comments?: string | null;
  created_by: Identifier;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  feedback: FeedbackSentiment;
  filename: string;
  tenant_id: Identifier;
  updated_by: Identifier;
}

export interface LabReportPiiRecord {
  patient_unique_id: Identifier;
  unique_id: Identifier;
  filename: string;
  created_by: Identifier;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  pii: JsonObject[];
  tenant_id: Identifier;
  updated_by: Identifier;
}

export interface LabReportExtractorRecord {
  patient_unique_id: Identifier;
  unique_id: Identifier;
  report_id: Identifier;
  created_by: Identifier;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  form_data: JsonObject[];
  tenant_id: Identifier;
  updated_by: Identifier;
}

export interface RegistrationRequestRecord {
  login: Identifier;
  unique_id: Identifier;
  created_by: Identifier;
  date_created: ISODateTime;
  date_updated: ISODateTime;
  email: ContactPoint[];
  name: string;
  phone: ContactPoint[];
  status: RequestStatus;
  updated_by: Identifier;
}

export type ProviderRegistrationRequestRecord = RegistrationRequestRecord;
export type UserRequestRecord = RegistrationRequestRecord;

export type DashboardMetricKey =
  | "organizations"
  | "providers"
  | "patients"
  | "heart_recordings"
  | "lung_recordings"
  | "lab_reports"
  | "qrisk_screenings"
  | "normal_heart_sound_reports"
  | "murmur_heart_sound_reports";

export interface DateRange {
  date_from: ISODate;
  date_to: ISODate;
}

export interface MetricPoint {
  date: ISODate;
  value: number;
}

export interface DashboardMetric {
  key: DashboardMetricKey;
  label: string;
  total: number;
  change_percent?: number | null;
  series: MetricPoint[];
}

export interface PipelineHealth {
  total: number;
  completed: number;
  processing: number;
  pending: number;
  failed: number;
  success_rate: number;
}

export interface BackupHealth {
  total_recordings: number;
  backed_up_recordings: number;
  missing_backups: number;
  coverage_percent: number;
  average_delay_seconds?: number | null;
}

export interface SubscriptionSummary {
  points_consumed: number;
  transaction_count: number;
  average_points_per_event: number;
}

export interface OnboardingSummary {
  pending: number;
  approved: number;
  rejected: number;
  oldest_pending_days?: number | null;
}

export interface FeedbackSummary {
  total: number;
  positive: number;
  neutral: number;
  negative: number;
  positive_percent: number;
}

export interface DataQualitySummary {
  total_issues: number;
  missing_coordinates: number;
  missing_provider_contacts: number;
  orphaned_phr_records: number;
  unmatched_lab_reports: number;
  recordings_without_backup: number;
}

export interface ActivitySummary {
  records_created: number;
  records_updated: number;
  active_providers: number;
  active_organizations: number;
}

export interface DashboardOverviewResponse {
  generated_at: ISODateTime;
  range: DateRange;
  metrics: DashboardMetric[];
  pipeline: PipelineHealth;
  backups: BackupHealth;
  subscriptions: SubscriptionSummary;
  onboarding: OnboardingSummary;
  feedback: FeedbackSummary;
  data_quality: DataQualitySummary;
  activity: ActivitySummary;
}

export interface ApiError {
  code: string;
  message: string;
  request_id?: string | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  integration_mode: string;
  timestamp: ISODateTime;
}

export interface OrganizationSummary {
  id: Identifier;
  name: string;
  city: string;
  state: string;
  country: string;
  status: RecordStatus;
  provider_count: number;
  patient_count: number;
  recording_count: number;
  date_created: ISODate;
}

export interface OrganizationListResponse {
  items: OrganizationSummary[];
  total: number;
  next_cursor?: string | null;
}

export interface ProviderSummary {
  id: Identifier;
  name: string;
  role: string;
  specialty: string;
  organization_id: Identifier;
  organization_name: string;
  status: RecordStatus;
  patient_count: number;
  date_created: ISODate;
}

export interface ProviderListResponse {
  items: ProviderSummary[];
  total: number;
  next_cursor?: string | null;
}

export interface LocationSummary {
  organization_id: Identifier;
  organization_name: string;
  city: string;
  state: string;
  country: string;
  location: GeoPoint;
  provider_count: number;
}

export interface LocationListResponse {
  items: LocationSummary[];
  total: number;
}

export interface ScopedDashboardResponse {
  scope_id: Identifier;
  scope_name: string;
  generated_at: ISODateTime;
  range: DateRange;
  metrics: DashboardMetric[];
}

export interface AihBuddyOverviewResponse {
  generated_at: ISODateTime;
  range: DateRange;
  total_screenings: number;
  completed_screenings: number;
  awaiting_review: number;
  high_risk_flags: number;
  active_providers: number;
  series: DashboardMetric[];
}

export interface OperationsOverviewResponse {
  generated_at: ISODateTime;
  range: DateRange;
  pipeline: PipelineHealth;
  backups: BackupHealth;
  subscriptions: SubscriptionSummary;
  onboarding: OnboardingSummary;
  feedback: FeedbackSummary;
  data_quality: DataQualitySummary;
}

export interface OrganizationCreateRequest {
  name: string;
  abdm_service_id?: string | null;
  address: string;
  city: string;
  state: string;
  country: string;
  pincode: string;
  location: GeoPoint;
}

export interface ProviderCreateRequest {
  login: Identifier;
  name: string;
  role: string;
  specialty: string;
  tenant_id: Identifier;
  address: string;
  city: string;
  state: string;
  country: string;
  pincode: string;
  location: GeoPoint;
  email: ContactPoint[];
  phone: ContactPoint[];
}

export interface OnboardingAcceptedResponse {
  request_id: Identifier;
  resource_type: string;
  status: string;
  persistence: string;
  submitted_at: ISODateTime;
}
