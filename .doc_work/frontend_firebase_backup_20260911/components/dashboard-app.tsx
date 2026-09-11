"use client";

import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { CSSProperties } from "react";
import { FirebaseLogin } from "@/components/firebase-login";
import { createOrganization, createProvider, DashboardClientError, exportDashboardSummary, getDashboard, getDashboardSession, getScopedDashboard, renewProviderSubscription } from "@/services/dashboard-client";
import type { AihBuddyView, BreakdownItemView, DashboardIdentity, DashboardMetricView, LocationView, MurmurBreakdownView, PatientBreakdownView, ReportingRange } from "@/lib/dashboard-contract";
import type { Clinician, Organization, UiIconName, View } from "@/lib/types";

type IconName = UiIconName;
type CustomCSSProperties = CSSProperties & Record<`--${string}`, string | number>;

type AnalyticsMetric = DashboardMetricView;
type ManagementDialog = "organization" | "clinician" | null;

const PAGE_SIZE = 10;

interface OverviewMetric {
  label: string;
  value: string;
  foot: string;
  icon: IconName;
  color: string;
  soft: string;
}

function metricStyle(color: string, soft: string): CustomCSSProperties {
  return { "--metric-color": color, "--metric-soft": soft };
}

function initials(name: string): string {
  return name.split(" ").filter(Boolean).slice(-2).map((part) => part.charAt(0).toUpperCase()).join("") || "U";
}

function roleLabel(role: string): string {
  return role.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function greetingForHour(hour: number): string {
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  return "Good evening";
}

function rangeForPeriod(period: string): ReportingRange {
  const dateTo = new Date();
  const dateFrom = new Date(dateTo);
  if (period === "Daily") return { dateFrom: isoDate(dateTo), dateTo: isoDate(dateTo) };
  if (period === "Current month") dateFrom.setUTCDate(1);
  else if (period === "Last 2 months") dateFrom.setUTCMonth(dateFrom.getUTCMonth() - 2);
  else if (period === "Last 3 months") dateFrom.setUTCMonth(dateFrom.getUTCMonth() - 3);
  else if (period === "Last year") dateFrom.setUTCFullYear(dateFrom.getUTCFullYear() - 1);
  else if (period === "All") return { dateFrom: "2018-01-01", dateTo: isoDate(dateTo) };
  else dateFrom.setUTCMonth(dateFrom.getUTCMonth() - 6);
  return { dateFrom: isoDate(dateFrom), dateTo: isoDate(dateTo) };
}

const paths = {
  dashboard:<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  building:<><path d="M4 21V5l8-3 8 3v16"/><path d="M9 21v-4h6v4M8 7h.01M12 7h.01M16 7h.01M8 11h.01M12 11h.01M16 11h.01"/></>,
  users:<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
  map:<><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/></>,
  plus:<><path d="M12 5v14M5 12h14"/></>, activity:<><path d="M3 12h4l3-8 4 16 3-8h4"/></>,
  shield:<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
  bell:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  menu:<><path d="M4 6h16M4 12h16M4 18h16"/></>, calendar:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></>,
  download:<><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14"/></>, search:<><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  heart:<><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/><path d="M3.5 12h4l2-4 3 8 2-4h6"/></>,
  lungs:<><path d="M12 3v9M10 7c-2 0-3 2-3 4v1c0 1-1 2-2 2-2 0-3 2-3 4s1 3 3 3c4 0 7-3 7-7M14 7c2 0 3 2 3 4v1c0 1 1 2 2 2 2 0 3 2 3 4s-1 3-3 3c-4 0-7-3-7-7"/></>,
  report:<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h6"/></>,
  patient:<><circle cx="12" cy="8" r="4"/><path d="M5 21a7 7 0 0 1 14 0M19 3v4M17 5h4"/></>,
  stethoscope:<><path d="M6 3v5a5 5 0 0 0 10 0V3M8 3H4M20 10a3 3 0 1 0 0 6h-1a4 4 0 0 0-4 4"/><circle cx="20" cy="10" r="1"/></>,
  chevron:<path d="m9 18 6-6-6-6"/>, logout:<><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></>,
  info:<><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></>,
} satisfies Record<IconName, ReactNode>;

function Icon({ name, size=18, className }: { name: IconName; size?: number; className?: string }) {
  return <svg className={className} aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

const nav: { id: View; label: string; icon: IconName; group?: string }[] = [
  { id:"hub", label:"Dashboard hub", icon:"dashboard", group:"Workspace" },
  { id:"overview", label:"AiSteth analytics", icon:"heart" },
  { id:"aih-buddy", label:"AiH Buddy", icon:"activity" },
  { id:"organizations", label:"Organizations", icon:"building" },
  { id:"clinicians", label:"Medical professionals", icon:"users" },
  { id:"locations", label:"Locations", icon:"map" },
  { id:"onboard-organization", label:"Add organization", icon:"plus", group:"Management" },
  { id:"onboard-clinician", label:"Invite professional", icon:"stethoscope" },
  { id:"activity", label:"Activity log", icon:"activity", group:"Governance" },
];

const viewTitles: Record<View,string> = {
  hub:"Dashboard hub", overview:"AiSteth operations overview", "aih-buddy":"AiH Buddy overview", organizations:"Organizations", "organization-detail":"Organization overview", clinicians:"Medical professionals", "clinician-detail":"Professional overview", locations:"Clinical network", "onboard-organization":"Onboard organization", "onboard-clinician":"Invite medical professional", activity:"Activity log",
};

export function DashboardApp() {
  const [view,setView] = useState<View>("overview");
  const [authState,setAuthState] = useState<"checking"|"authenticated"|"required"|"denied">("checking");
  const [menuOpen,setMenuOpen] = useState(false);
  const [sidebarCollapsed,setSidebarCollapsed] = useState(false);
  const [loading,setLoading] = useState(true);
  const [loadError,setLoadError] = useState("");
  const [period,setPeriod] = useState("Last 6 months");
  const [toast,setToast] = useState("");
  const [orgs,setOrgs] = useState<Organization[]>([]);
  const [clinicians,setClinicians] = useState<Clinician[]>([]);
  const [analyticsMetrics,setAnalyticsMetrics] = useState<AnalyticsMetric[]>([]);
  const [aihBuddy,setAihBuddy] = useState<AihBuddyView>({totalScreenings:0,completedScreenings:0,awaitingReview:0,highRiskFlags:0,activeProviders:0});
  const [patientBreakdown,setPatientBreakdown] = useState<PatientBreakdownView>({total:0,auscultationType:[],genderDistribution:[],ageGroupDistribution:[]});
  const [murmurBreakdown,setMurmurBreakdown] = useState<MurmurBreakdownView>({totalReports:0,genderDistribution:[],ageGroupDistribution:[]});
  const [locations,setLocations] = useState<LocationView[]>([]);
  const [generatedAt,setGeneratedAt] = useState("");
  const [selectedOrg,setSelectedOrg] = useState<Organization | null>(null);
  const [selectedClinician,setSelectedClinician] = useState<Clinician | null>(null);
  const [managementDialog,setManagementDialog] = useState<ManagementDialog>(null);
  const [identity,setIdentity] = useState<DashboardIdentity | null>(null);
  const [exportOpen,setExportOpen] = useState(false);
  const [renewalClinician,setRenewalClinician] = useState<Clinician | null>(null);
  const [pendingOrganizationIds,setPendingOrganizationIds] = useState<Set<string>>(()=>new Set());
  const pendingOrganizations = useRef(new Map<string,Organization>());
  const pendingClinicians = useRef(new Map<string,Clinician>());

  const refreshDashboard = useCallback(async (range: ReportingRange) => {
    setLoading(true);
    setLoadError("");
    try {
      const data = await getDashboard(range);
      const organizationIds=new Set(data.organizations.map((item)=>item.id));
      const clinicianIds=new Set(data.clinicians.map((item)=>item.id));
      for(const id of organizationIds)pendingOrganizations.current.delete(id);
      for(const id of clinicianIds)pendingClinicians.current.delete(id);
      for(const [id,pending] of pendingOrganizations.current){if(data.organizations.some((item)=>item.name.toLocaleLowerCase()===pending.name.toLocaleLowerCase()&&item.city.toLocaleLowerCase()===pending.city.toLocaleLowerCase()))pendingOrganizations.current.delete(id)}
      for(const [id,pending] of pendingClinicians.current){if(data.clinicians.some((item)=>item.name.toLocaleLowerCase()===pending.name.toLocaleLowerCase()&&item.organization.toLocaleLowerCase()===pending.organization.toLocaleLowerCase()))pendingClinicians.current.delete(id)}
      setPendingOrganizationIds(new Set(pendingOrganizations.current.keys()));
      setOrgs([...pendingOrganizations.current.values(),...data.organizations]);
      setClinicians([...pendingClinicians.current.values(),...data.clinicians]);
      setAnalyticsMetrics(data.metrics);
      setAihBuddy(data.aihBuddy);
      setPatientBreakdown(data.patientBreakdown);
      setMurmurBreakdown(data.murmurBreakdown);
      setLocations(data.locations);
      setGeneratedAt(data.generatedAt);
      setAuthState("authenticated");
    } catch (error: unknown) {
      if (error instanceof DashboardClientError && error.status === 401) setAuthState("required");
      else if (error instanceof DashboardClientError && error.status === 403) setAuthState("denied");
      else setLoadError("Dashboard data is temporarily unavailable. Please retry shortly.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active=true;
    const watchdog=window.setTimeout(()=>{if(active){setAuthState("required");setLoading(false)}},10_000);
    void (async()=>{
      const session=await getDashboardSession();
      if(!active)return;
      window.clearTimeout(watchdog);
      if(session){setIdentity(session);setAuthState("authenticated");await refreshDashboard(rangeForPeriod("Last 6 months"));}
      else{setAuthState("required");setLoading(false)}
    })();
    return ()=>{active=false;window.clearTimeout(watchdog)};
  },[refreshDashboard]);
  useEffect(() => { if (!toast) return; const timer=setTimeout(()=>setToast(""),3200); return ()=>clearTimeout(timer); },[toast]);

  function navigate(next:View) {
    setMenuOpen(false);
    if(next==="onboard-organization"&&!canManageOrganizations){setToast("Only a super admin can add an organization.");return;}
    if(next==="onboard-clinician"&&!canManageProfessionals){setToast("You do not have permission to invite a professional.");return;}
    if (next === "onboard-organization") { setManagementDialog("organization"); return; }
    if (next === "onboard-clinician") { setManagementDialog("clinician"); return; }
    setView(next);
    window.scrollTo({top:0,behavior:"smooth"});
  }
  function toggleSidebar() {
    if (window.innerWidth <= 820) setMenuOpen((open)=>!open);
    else setSidebarCollapsed((collapsed)=>!collapsed);
  }
  function refreshAfterDatabaseProjection(){for(const delay of [3000,10000,30000])window.setTimeout(()=>{void refreshDashboard(rangeForPeriod(period))},delay)}
  const normalizedRole=identity?.role.trim().toLowerCase().replaceAll("_","")??"";
  const isSuperAdmin=normalizedRole==="superadmin";
  const isTenantAdmin=normalizedRole==="admin"||normalizedRole==="tenantadmin";
  const canManageOrganizations=authState==="authenticated"&&isSuperAdmin;
  const canManageProfessionals=authState==="authenticated"&&(isSuperAdmin||isTenantAdmin);
  const canManage=canManageProfessionals;

  if(authState==="checking") return <div className="auth-screen"><section className="auth-card card" aria-live="polite"><span className="auth-mark"><Icon name="shield" size={34}/></span><p className="eyebrow">Secure administration</p><h1>Verifying access</h1><p>Checking your signed-in session.</p></section></div>;

  if(authState==="required"||authState==="denied") return <div className="auth-screen"><section className="auth-card card"><span className="auth-mark"><Icon name="stethoscope" size={34}/></span><p className="eyebrow">Secure administration</p><h1>{authState==="denied"?"Dashboard access denied":"Sign in to AiSteth"}</h1><p>{authState==="denied"?"Your account does not have the required dashboard role or tenant scope.":"Sign in with your AiSteth account to continue."}</p>{authState==="required"?<FirebaseLogin/>:<form action="/api/auth/logout" method="post"><button className="button auth-button" type="submit">Sign out</button></form>}</section></div>;

  const displayName=identity?.name||identity?.login||"Signed-in user";
  const displayRole=identity?.role?roleLabel(identity.role):"Dashboard user";
  const displayInitials=initials(displayName);

  return <div className={`app-shell ${sidebarCollapsed?"sidebar-collapsed":""}`}>
    <div className={`mobile-overlay ${menuOpen?"open":""}`} onClick={()=>setMenuOpen(false)} />
    <aside className={`sidebar ${menuOpen?"open":""}`} aria-label="Primary navigation">
      <div className="brand"><div className="brand-mark"><Icon name="stethoscope" size={27}/></div><div className="brand-copy"><div className="brand-name">AiSteth</div><div className="brand-sub">Clinical operations</div></div></div>
      <nav className="nav">
        {nav.filter((item)=>isSuperAdmin||!(["aih-buddy","activity"] as View[]).includes(item.id)).filter((item)=>item.id!=="onboard-organization"||canManageOrganizations).filter((item)=>item.id!=="onboard-clinician"||canManageProfessionals).map((item)=><div key={item.id}>{item.group&&<div className="nav-label">{item.group}</div>}<button title={item.label} className={`nav-button ${view===item.id?"active":""}`} onClick={()=>navigate(item.id)} aria-current={view===item.id?"page":undefined}><Icon className="nav-icon" name={item.icon}/><span className="nav-text">{item.label}</span></button></div>)}
      </nav>
      <div className="sidebar-foot"><div className="privacy-note"><Icon name="shield" size={19}/><div className="security-copy"><strong>Data security</strong><span>Only aggregate operational data is displayed. Connection credentials remain server-side.</span><button>Learn more <Icon name="chevron" size={13}/></button></div></div><div className="sidebar-user"><div className="sidebar-avatar">{displayInitials}</div><div className="sidebar-user-copy"><strong>{displayName}</strong><span>{displayRole}</span></div><Icon className="sidebar-chevron" name="chevron" size={14}/></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <button className="mobile-menu" aria-label={sidebarCollapsed?"Expand navigation":"Collapse navigation"} onClick={toggleSidebar}><Icon name="menu"/></button>
        <div className="top-title"><h1>{viewTitles[view]}</h1><p>AiSteth administration · Aggregate operational data</p></div>
        <div className="top-actions">
          <button className="icon-button" aria-label="Notifications" onClick={()=>setToast("Operational notifications are available in the activity view")}><Icon name="bell" size={17}/><span className="notification-dot"/></button>
          <form action="/api/auth/logout" method="post"><button className="button compact" type="submit"><Icon name="logout" size={15}/>Sign out</button></form>
          <div className="user"><div className="avatar">{displayInitials}</div><div><strong>{displayName}</strong><span>{identity?.login}</span></div></div>
        </div>
      </header>
      <main>
        {view==="hub"&&<DashboardHub navigate={navigate} canAddOrganization={canManageOrganizations} canInviteProfessional={canManageProfessionals}/>} 
        {view==="overview"&&<Overview userName={displayName} loading={loading} loadError={loadError} period={period} setPeriod={setPeriod} orgs={orgs} metrics={analyticsMetrics} patientBreakdown={patientBreakdown} murmurBreakdown={murmurBreakdown} canAddOrganization={canManageOrganizations} generatedAt={generatedAt} onRangeChange={refreshDashboard} navigate={navigate} openExport={()=>setExportOpen(true)} openOrg={(org)=>{setSelectedOrg(org);navigate("organization-detail")}}/>} 
        {view==="aih-buddy"&&<AihBuddyDashboard data={aihBuddy} metrics={analyticsMetrics} loading={loading} onRangeChange={refreshDashboard} setToast={setToast}/>} 
        {view==="organizations"&&<Organizations orgs={orgs} navigate={navigate} canAdd={canManageOrganizations} openOrg={(org)=>{setSelectedOrg(org);navigate("organization-detail")}}/>} 
        {view==="organization-detail"&&selectedOrg&&<OrganizationDetail organization={selectedOrg} clinicians={clinicians.filter(c=>c.organization===selectedOrg.name)} back={()=>navigate("organizations")} openClinician={(clinician)=>{setSelectedClinician(clinician);navigate("clinician-detail")}} setToast={setToast}/>} 
        {view==="clinicians"&&<Clinicians clinicians={clinicians} navigate={navigate} canInvite={canManageProfessionals} openClinician={(clinician)=>{setSelectedClinician(clinician);navigate("clinician-detail")}}/>} 
        {view==="clinician-detail"&&selectedClinician&&<ClinicianDetail clinician={selectedClinician} organizations={orgs} back={()=>navigate("clinicians")} onRenew={()=>setRenewalClinician(selectedClinician)}/>} 
        {view==="locations"&&<Locations locations={locations}/>} 
        {view==="activity"&&<ActivityLog/>}
      </main>
    </div>
    {managementDialog==="organization"&&<Modal title="Add organization" onClose={()=>setManagementDialog(null)}><OrganizationForm disabled={!canManage} onToast={setToast} onCreated={(organization)=>{pendingOrganizations.current.set(organization.id,organization);setPendingOrganizationIds((ids)=>new Set(ids).add(organization.id));setOrgs((items)=>[organization,...items.filter((item)=>item.id!==organization.id)]);setManagementDialog(null);setView("organizations");setToast(`${organization.name} was saved to the database.`);refreshAfterDatabaseProjection()}}/></Modal>}
    {managementDialog==="clinician"&&<Modal title="Invite professional" onClose={()=>setManagementDialog(null)}><ClinicianForm organizations={orgs.filter((item)=>!pendingOrganizationIds.has(item.id))} disabled={!canManage} onToast={setToast} onCreated={(clinician)=>{pendingClinicians.current.set(clinician.id,clinician);setClinicians((items)=>[clinician,...items.filter((item)=>item.id!==clinician.id)]);setManagementDialog(null);setView("clinicians");setToast(`${clinician.name} was saved to the database with an active subscription.`);refreshAfterDatabaseProjection()}}/></Modal>}
    {exportOpen&&<Modal title="Export summary" onClose={()=>setExportOpen(false)}><SummaryExport organizations={orgs} range={rangeForPeriod(period)} email={identity?.login||""} onClose={()=>setExportOpen(false)} onQueued={(count)=>setToast(`Summary report emailed successfully for ${count} organization${count===1?"":"s"}.`)}/></Modal>}
    {renewalClinician&&<Modal title="Renew subscription" onClose={()=>setRenewalClinician(null)}><SubscriptionRenewal clinician={renewalClinician} onClose={()=>setRenewalClinician(null)} onRenewed={()=>{setRenewalClinician(null);setToast(`Subscription renewed for ${renewalClinician.name}.`);navigate("clinicians");void refreshDashboard(rangeForPeriod(period))}}/></Modal>}
    {toast&&<div className="toast" role="status" aria-live="polite"><span className="toast-icon"><Icon name="shield" size={16}/></span><span>{toast}</span></div>}
  </div>;
}

function PageHeading({ eyebrow, title, description, children }:{eyebrow:string;title:string;description:string;children?:ReactNode}) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><p>{description}</p></div>{children&&<div className="heading-actions">{children}</div>}</div>;
}

function Modal({title,onClose,children}:{title:string;onClose:()=>void;children:ReactNode}) {
  useEffect(()=>{
    const previousOverflow=document.body.style.overflow;
    const closeOnEscape=(event:KeyboardEvent)=>{if(event.key==="Escape")onClose()};
    document.body.style.overflow="hidden";
    window.addEventListener("keydown",closeOnEscape);
    return ()=>{document.body.style.overflow=previousOverflow;window.removeEventListener("keydown",closeOnEscape)};
  },[onClose]);
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="modal-panel" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event)=>event.stopPropagation()}><button type="button" className="modal-close" onClick={onClose} aria-label={`Close ${title}`}>×</button>{children}</section></div>;
}

function SummaryExport({organizations,range,email,onClose,onQueued}:{organizations:Organization[];range:ReportingRange;email:string;onClose:()=>void;onQueued:(count:number)=>void}) {
  const [query,setQuery]=useState("");
  const [selected,setSelected]=useState<Set<string>>(()=>new Set());
  const [submitting,setSubmitting]=useState(false);
  const [error,setError]=useState("");
  const visible=organizations.filter((organization)=>`${organization.name} ${organization.city} ${organization.state} ${organization.country}`.toLowerCase().includes(query.trim().toLowerCase()));
  const allVisibleSelected=visible.length>0&&visible.every((organization)=>selected.has(organization.id));
  function toggle(id:string) {
    setSelected((current)=>{const next=new Set(current);if(next.has(id))next.delete(id);else next.add(id);return next});
  }
  function toggleVisible() {
    setSelected((current)=>{const next=new Set(current);for(const organization of visible){if(allVisibleSelected)next.delete(organization.id);else next.add(organization.id)}return next});
  }
  async function submit(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(selected.size===0){setError("Select at least one organization.");return}
    setSubmitting(true);setError("");
    try {
      await exportDashboardSummary([...selected],range);
      onQueued(selected.size);
      onClose();
    } catch (caught:unknown) {
      if(caught instanceof DashboardClientError&&caught.status===401)setError("Your session expired. Sign in again and retry.");
      else if(caught instanceof DashboardClientError&&caught.status===403)setError("Your account is not allowed to export reports.");
      else setError("The report could not be queued. Check the report service configuration and retry.");
    } finally {setSubmitting(false)}
  }
  return <form className="summary-export" onSubmit={submit}>
    <div className="summary-export-head"><p className="eyebrow">Patient report export</p><h2>Select organizations</h2><p>Choose the organizations to include. The existing report service will email the export to <strong>{email}</strong>.</p></div>
    <div className="summary-export-toolbar"><div className="search-wrap"><Icon name="search" size={15}/><input className="search" value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="Search organizations" aria-label="Search organizations to export"/></div><button className="button compact" type="button" onClick={toggleVisible} disabled={visible.length===0}>{allVisibleSelected?"Clear visible":"Select visible"}</button></div>
    <div className="summary-export-list" role="group" aria-label="Organizations included in export">
      {visible.map((organization)=><label className="summary-export-option" key={organization.id}><input type="checkbox" checked={selected.has(organization.id)} onChange={()=>toggle(organization.id)}/><span className="org-logo">{organization.code}</span><span><strong>{organization.name}</strong><small>{organization.city}, {organization.state}</small></span></label>)}
      {visible.length===0&&<div className="empty"><strong>No organizations found</strong>Try another search term.</div>}
    </div>
    {error&&<div className="notice" role="alert"><Icon name="info" size={16}/><span>{error}</span></div>}
    <div className="summary-export-actions"><span>{selected.size} selected</span><div><button className="button" type="button" onClick={onClose} disabled={submitting}>Cancel</button><button className="button primary" type="submit" disabled={submitting||selected.size===0}><Icon name="download" size={15}/>{submitting?"Queueing…":"Export and email"}</button></div></div>
  </form>;
}

function SubscriptionRenewal({clinician,onClose,onRenewed}:{clinician:Clinician;onClose:()=>void;onRenewed:()=>void}) {
  const [duration,setDuration]=useState<1|3>(1);
  const [submitting,setSubmitting]=useState(false);
  const [error,setError]=useState("");
  async function submit(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();setSubmitting(true);setError("");
    try {await renewProviderSubscription(clinician.id,duration);onRenewed()}
    catch (caught:unknown) {
      if(caught instanceof DashboardClientError&&caught.status===401)setError("Your session expired. Sign in again and retry.");
      else if(caught instanceof DashboardClientError&&caught.status===403)setError("Your account is not allowed to renew subscriptions.");
      else setError("The subscription could not be renewed. Please retry.");
    } finally {setSubmitting(false)}
  }
  return <form className="subscription-renewal" onSubmit={submit}><div><p className="eyebrow">Subscription management</p><h2>Renew {clinician.name}</h2><p>{clinician.organization}</p></div><div className="subscription-current"><span>Current status</span><strong className={`subscription-text ${clinician.subscriptionStatus.toLowerCase()}`}>{clinician.subscriptionStatus}</strong><span>Current plan</span><strong>{clinician.subscriptionPlan||"No active plan"}</strong><span>Ends</span><strong>{clinician.subscriptionEndDate?new Date(clinician.subscriptionEndDate).toLocaleDateString("en-IN"):"—"}</strong></div><label className="form-field">Renewal period<select value={duration} onChange={(event)=>setDuration(Number(event.target.value)===3?3:1)}><option value={1}>1 year</option><option value={3}>3 years</option></select><small>An active plan is extended from its current end date; otherwise it starts today.</small></label>{error&&<div className="notice" role="alert"><Icon name="info" size={16}/><span>{error}</span></div>}<div className="form-actions"><button type="button" className="button" onClick={onClose} disabled={submitting}>Cancel</button><button type="submit" className="button primary" disabled={submitting}>{submitting?"Renewing…":"Renew subscription"}</button></div></form>;
}

function Pagination({page,total,onPageChange,label}:{page:number;total:number;onPageChange:(page:number)=>void;label:string}) {
  const pageCount=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if(total<=PAGE_SIZE)return null;
  const currentPage=Math.min(page,pageCount);
  const first=(currentPage-1)*PAGE_SIZE+1;
  const last=Math.min(currentPage*PAGE_SIZE,total);
  const pageNumbers=Array.from(new Set([1,currentPage-1,currentPage,currentPage+1,pageCount])).filter((pageNumber)=>pageNumber>=1&&pageNumber<=pageCount).sort((a,b)=>a-b);
  return <nav className="pagination" aria-label={`${label} pagination`}><span>Showing {first}–{last} of {total}</span><div className="page-buttons"><button type="button" onClick={()=>onPageChange(currentPage-1)} disabled={currentPage===1} aria-label="Previous page">‹</button>{pageNumbers.map((pageNumber)=><button type="button" key={pageNumber} className={pageNumber===currentPage?"active":""} aria-current={pageNumber===currentPage?"page":undefined} onClick={()=>onPageChange(pageNumber)}>{pageNumber}</button>)}<button type="button" onClick={()=>onPageChange(currentPage+1)} disabled={currentPage===pageCount} aria-label="Next page">›</button></div></nav>;
}

function pageItems<T>(items:readonly T[],page:number):readonly T[] {
  const pageCount=Math.max(1,Math.ceil(items.length/PAGE_SIZE));
  const currentPage=Math.min(page,pageCount);
  return items.slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);
}

function DashboardHub({navigate,canAddOrganization,canInviteProfessional}:{navigate:(v:View)=>void;canAddOrganization:boolean;canInviteProfessional:boolean}) {
  const cards: ReadonlyArray<{title:string;description:string;icon:IconName;target:View;color:string}>=[
    {title:"AiSteth",description:"Complete network analytics for organizations, professionals, patients, recordings, reports and heart-sound AI results.",icon:"stethoscope",target:"overview",color:"#2364c4"},
    {title:"AiH Buddy",description:"QRisk screening volume and program activity across the selected reporting period.",icon:"activity",target:"aih-buddy",color:"#7c5bb5"},
    {title:"Onboard organization",description:"Open the organization onboarding form and review the required operational fields.",icon:"building",target:"onboard-organization",color:"#178a62"},
    {title:"Onboard professional",description:"Prepare an invitation for a doctor or nurse and assign an organization.",icon:"users",target:"onboard-clinician",color:"#c66756"},
  ];
  const visibleCards=cards.filter((card)=>card.target!=="aih-buddy"||canAddOrganization).filter((card)=>card.target!=="onboard-organization"||canAddOrganization).filter((card)=>card.target!=="onboard-clinician"||canInviteProfessional);
  return <div className="page"><PageHeading eyebrow="Administration" title="Choose a workspace" description="Access product dashboards and onboarding workflows from one place."/><div className="hub-grid">{visibleCards.map(card=><button className="hub-card card" key={card.title} onClick={()=>navigate(card.target)}><span className="hub-icon" style={{color:card.color,background:`${card.color}16`}}><Icon name={card.icon} size={26}/></span><span><strong>{card.title}</strong><small>{card.description}</small></span><Icon name="chevron" size={18}/></button>)}</div></div>;
}

function DateFilter({period,setPeriod,onRangeChange,generatedAt}:{period:string;setPeriod:(v:string)=>void;onRangeChange?:(range:ReportingRange)=>void;generatedAt?:string}) {
  const custom=period==="Custom";
  const defaults=rangeForPeriod("Last 6 months");
  const [dateFrom,setDateFrom]=useState(defaults.dateFrom);
  const [dateTo,setDateTo]=useState(defaults.dateTo);
  const refreshed=generatedAt ? new Date(generatedAt).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}) : "Not refreshed";
  function selectPeriod(value:string) {
    setPeriod(value);
    if(value!=="Custom") onRangeChange?.(rangeForPeriod(value));
  }
  function applyCustom() {
    if(dateFrom&&dateTo&&dateFrom<=dateTo) onRangeChange?.({dateFrom,dateTo});
  }
  return <div className="toolbar date-toolbar"><div className="toolbar-label"><Icon name="calendar" size={17}/>Reporting period</div><select className="field-compact" value={period} onChange={e=>selectPeriod(e.target.value)}><option>All</option><option>Daily</option><option>Current month</option><option>Last 2 months</option><option>Last 3 months</option><option>Last 6 months</option><option>Last year</option><option>Custom</option></select>{custom&&<><label className="date-field">From<input type="date" value={dateFrom} onChange={event=>setDateFrom(event.target.value)}/></label><label className="date-field">To<input type="date" value={dateTo} onChange={event=>setDateTo(event.target.value)}/></label><button type="button" className="button primary compact" onClick={applyCustom}>Apply</button></>}<span className="updated">Last refreshed {refreshed}</span></div>;
}

const breakdownColors=["#8e70cf","#ff8765","#45a3e8","#ff5d7f","#f5bf4f","#75bf78","#b3c1c7"];

function BreakdownChart({title,items}:{title:string;items:readonly BreakdownItemView[]}) {
  const stops=items.map((item,index)=>{const start=items.slice(0,index).reduce((sum,current)=>sum+current.percentage,0);const end=start+item.percentage;return `${breakdownColors[index%breakdownColors.length]} ${start}% ${end}%`}).join(",");
  return <section className="breakdown-chart"><h3>{title}</h3><div className="pie-chart" style={{background:stops?`conic-gradient(${stops})`:"#e8edf4"}} role="img" aria-label={`${title} pie chart`}/><div className="breakdown-legend">{items.map((item,index)=><div key={item.label}><span style={{background:breakdownColors[index%breakdownColors.length]}}/><p>{item.label}: <strong>{item.count.toLocaleString("en-IN")}</strong> ({item.percentage.toFixed(1)}%)</p></div>)}</div></section>;
}

function PatientBreakdownModal({data,onClose}:{data:PatientBreakdownView;onClose:()=>void}) {
  return <Modal title="Patient statistics" onClose={onClose}><div className="patient-breakdown"><div className="breakdown-summary"><p className="eyebrow">Connected patient data</p><strong>{data.total.toLocaleString("en-IN")}</strong><span>patients in the selected reporting period</span></div><div className="breakdown-grid"><BreakdownChart title="Auscultation type" items={data.auscultationType}/><BreakdownChart title="Gender distribution" items={data.genderDistribution}/><BreakdownChart title="Age group distribution" items={data.ageGroupDistribution}/></div></div></Modal>;
}

function MetricDetailModal({metric,patientBreakdown,murmurBreakdown,onClose}:{metric:AnalyticsMetric;patientBreakdown?:PatientBreakdownView|undefined;murmurBreakdown?:MurmurBreakdownView|undefined;onClose:()=>void}) {
  if(metric.key==="patients"&&patientBreakdown)return <PatientBreakdownModal data={patientBreakdown} onClose={onClose}/>;
  if(metric.key==="murmur"&&murmurBreakdown)return <Modal title="Murmur patient statistics" onClose={onClose}><div className="patient-breakdown"><div className="breakdown-summary"><p className="eyebrow">Murmur AI reports</p><strong>{murmurBreakdown.totalReports.toLocaleString("en-IN")}</strong><span>reports in the selected period</span></div><div className="breakdown-grid two-columns"><BreakdownChart title="Murmur gender distribution" items={murmurBreakdown.genderDistribution}/><BreakdownChart title="Murmur age distribution" items={murmurBreakdown.ageGroupDistribution}/></div></div></Modal>;
  return null;
}

function AnalyticsGrid({metrics=[],scope="network",exclude=[],patientBreakdown,murmurBreakdown}:{metrics?:readonly AnalyticsMetric[];scope?:string;exclude?:string[];patientBreakdown?:PatientBreakdownView;murmurBreakdown?:MurmurBreakdownView}) {
  const [selectedMetric,setSelectedMetric]=useState<AnalyticsMetric|null>(null);
  const displayed=metrics.filter(metric=>!exclude.includes(metric.key));
  return <section className="analytics-section"><div className="section-title"><div><h3>Detailed analytics</h3><p>Aggregate reporting streams for this {scope}. Hover over Registered patients or Murmur HS AI reports for demographic statistics.</p></div><span className="pill">{displayed.length} connected charts</span></div><div className="analytics-grid">{displayed.map((metric)=>{const interactive=(metric.key==="patients"&&patientBreakdown!==undefined)||(metric.key==="murmur"&&murmurBreakdown!==undefined);return <div key={metric.key} className={interactive?"interactive-chart":undefined} tabIndex={interactive?0:undefined} role={interactive?"button":undefined} aria-label={interactive?`Open ${metric.label} statistics`:undefined} onMouseEnter={interactive?()=>setSelectedMetric(metric):undefined} onFocus={interactive?()=>setSelectedMetric(metric):undefined} onClick={interactive?()=>setSelectedMetric(metric):undefined}><MetricChart metric={metric}/></div>})}</div>{selectedMetric&&<MetricDetailModal metric={selectedMetric} patientBreakdown={patientBreakdown} murmurBreakdown={murmurBreakdown} onClose={()=>setSelectedMetric(null)}/>}</section>;
}

function MetricChart({metric}:{metric:AnalyticsMetric}) {
  const max=Math.max(...metric.series); const min=Math.min(...metric.series); const range=max-min||1; const points=metric.series.map((v,i)=>`${18+i*47},${112-(v-min)/range*75}`).join(" ");
  return <article className="card analytics-card" style={metricStyle(metric.color,metric.soft)}><div className="analytics-card-head"><span className="metric-icon"><Icon name={metric.icon} size={19}/></span><div><span>{metric.label}</span><strong>{metric.value}</strong></div><span className="trend-up">{metric.changePercent===null?"Period trend":`${metric.changePercent>=0?"↑":"↓"} ${Math.abs(metric.changePercent).toFixed(1)}%`}</span></div><svg viewBox="0 0 320 145" role="img" aria-label={`${metric.label} trend chart`}><defs><linearGradient id={`gradient-${metric.key}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={metric.color} stopOpacity=".25"/><stop offset="1" stopColor={metric.color} stopOpacity="0"/></linearGradient></defs>{[37,62,87,112].map(y=><line key={y} x1="18" y1={y} x2="302" y2={y} className="chart-grid"/>)}<polygon points={`${points} 300,125 18,125`} fill={`url(#gradient-${metric.key})`}/><polyline points={points} fill="none" stroke={metric.color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"/>{metric.series.map((value,i)=>{const y=112-(value-min)/range*75;return <circle key={i} cx={18+i*47} cy={y} r="3" fill="#fff" stroke={metric.color} strokeWidth="2"/>})}<g>{metric.labels.map((label,i)=><text key={`${label}-${i}`} x={10+i*47} y="141" className="chart-label">{label}</text>)}</g></svg></article>;
}

function AihBuddyDashboard({data,metrics,loading,onRangeChange,setToast}:{data:AihBuddyView;metrics:readonly AnalyticsMetric[];loading:boolean;onRangeChange:(range:ReportingRange)=>void;setToast:(s:string)=>void}) {
  const [period,setPeriod]=useState("All");
  const qriskMetric=metrics.find((metric)=>metric.key==="qrisk");
  return <div className="page">
    <PageHeading eyebrow="AiH Buddy" title="QRisk screening overview" description="Monitor aggregate cardiovascular-risk workflow usage."><button className="button" onClick={()=>setToast("Aggregate report prepared")}><Icon name="download" size={15}/>Download report</button></PageHeading>
    <DateFilter period={period} setPeriod={setPeriod} onRangeChange={onRangeChange}/>
    <section className="buddy-hero card"><div><span className="metric-icon"><Icon name="activity" size={26}/></span><p>Total QRisk screenings</p><strong>{loading?"—":data.totalScreenings.toLocaleString("en-IN")}</strong><small>Aggregate screening activity</small></div><div className="buddy-chart">{qriskMetric?<MetricChart metric={qriskMetric}/>:<div className="empty">No screening trend is available.</div>}</div></section>
    <div className="section-title"><div><h3>Screening breakdown</h3><p>Operational summary for the selected period</p></div></div>
    <section className="metrics"><DetailMetric label="Completed screenings" value={data.completedScreenings.toLocaleString("en-IN")} icon="shield"/><DetailMetric label="Awaiting review" value={data.awaitingReview.toLocaleString("en-IN")} icon="report"/><DetailMetric label="High-risk flags" value={data.highRiskFlags.toLocaleString("en-IN")} icon="heart"/><DetailMetric label="Active professionals" value={data.activeProviders.toLocaleString("en-IN")} icon="users"/></section>
  </div>;
}

function Overview({userName,loading,loadError,period,setPeriod,orgs,metrics,patientBreakdown,murmurBreakdown,canAddOrganization,generatedAt,onRangeChange,navigate,openExport,openOrg}:{userName:string;loading:boolean;loadError:string;period:string;setPeriod:(v:string)=>void;orgs:Organization[];metrics:readonly AnalyticsMetric[];patientBreakdown:PatientBreakdownView;murmurBreakdown:MurmurBreakdownView;canAddOrganization:boolean;generatedAt:string;onRangeChange:(range:ReportingRange)=>void;navigate:(v:View)=>void;openExport:()=>void;openOrg:(o:Organization)=>void}) {
  const [page,setPage]=useState(1);
  const [greeting,setGreeting]=useState(()=>greetingForHour(new Date().getHours()));
  useEffect(()=>{const update=()=>setGreeting(greetingForHour(new Date().getHours()));update();const timer=window.setInterval(update,60_000);return()=>window.clearInterval(timer)},[]);
  const byKey=(key:string)=>metrics.find((metric)=>metric.key===key);
  const heart=Number((byKey("heart")?.value??"0").replaceAll(",",""));
  const lung=Number((byKey("lung")?.value??"0").replaceAll(",",""));
  const summary:readonly OverviewMetric[]=[
    {label:"Organizations",value:byKey("organizations")?.value??"0",foot:canAddOrganization?"Connected aggregate":"Assigned tenant scope",icon:"building",color:"#2364c4",soft:"#edf5ff"},
    {label:"Medical professionals",value:byKey("doctors")?.value??"0",foot:"Connected aggregate",icon:"stethoscope",color:"#3b7f78",soft:"#eaf6f4"},
    {label:"Registered patients",value:byKey("patients")?.value??"0",foot:"Aggregate count",icon:"patient",color:"#7c5bb5",soft:"#f2edfa"},
    {label:"Total recordings",value:new Intl.NumberFormat("en-IN").format(heart+lung),foot:"Heart and lung",icon:"heart",color:"#c66756",soft:"#fbefec"},
  ];
  return <div className="page">
    <PageHeading eyebrow="Network intelligence" title={`${greeting}, ${userName.split(/\s+/)[0]}`} description="Monitor adoption, recordings, and operational health across the AiSteth network."><button className="button" onClick={openExport}><Icon name="download" size={15}/>Export summary</button>{canAddOrganization&&<button className="button primary" onClick={()=>navigate("onboard-organization")}><Icon name="plus" size={15}/>Add organization</button>}</PageHeading>
    <DateFilter period={period} setPeriod={setPeriod} onRangeChange={onRangeChange} generatedAt={generatedAt}/>
    {loadError&&<div className="notice" role="alert"><Icon name="info" size={16}/><span>{loadError}</span><button type="button" className="button compact" onClick={()=>onRangeChange(rangeForPeriod(period))}>Retry</button></div>}
    <section className="metrics" aria-label="Key metrics">{summary.map((metric)=><div className="metric" key={metric.label} style={metricStyle(metric.color,metric.soft)}><div className="metric-main"><span className="metric-icon"><Icon name={metric.icon} size={22}/></span><div><div className="metric-label">{metric.label}</div><div className={loading?"metric-value loading":"metric-value"}>{loading?"—":metric.value}</div></div></div><div className="metric-foot">{metric.foot}</div></div>)}</section>
    <AnalyticsGrid metrics={metrics} patientBreakdown={patientBreakdown} murmurBreakdown={murmurBreakdown}/>
    <section className="card table-card"><div className="card-head"><div><h3>Organizations</h3><p>Aggregate organization directory</p></div></div><div className="table-scroll"><table><thead><tr><th>Organization</th><th>Created</th><th>Location</th><th>Professionals</th><th>Status</th><th></th></tr></thead><tbody>{pageItems(orgs,page).map((organization)=><tr key={organization.id}><td><div className="org-cell"><span className="org-logo">{organization.code}</span>{organization.name}</div></td><td>{organization.created}</td><td>{organization.city}, {organization.state}</td><td>{organization.clinicians}</td><td><span className={`status ${organization.status==="Active"?"active":"review"}`}>{organization.status}</span></td><td><button type="button" className="table-action" onClick={()=>openOrg(organization)}>View <Icon name="chevron" size={11}/></button></td></tr>)}</tbody></table></div>{!loading&&orgs.length===0&&<div className="empty"><strong>No organizations available</strong>The connected service returned no organization summaries.</div>}<Pagination page={page} total={orgs.length} onPageChange={setPage} label="Overview organizations"/></section>
  </div>;
}

function Organizations({orgs,navigate,openOrg,canAdd}:{orgs:Organization[];navigate:(v:View)=>void;openOrg:(o:Organization)=>void;canAdd:boolean}) {
  const [query,setQuery]=useState("");
  const [page,setPage]=useState(1);
  const normalizedQuery=query.trim().toLowerCase();
  const visible=orgs.filter((organization)=>`${organization.code} ${organization.name} ${organization.city} ${organization.state} ${organization.country} ${organization.status} ${organization.created}`.toLowerCase().includes(normalizedQuery));
  return <div className="page"><PageHeading eyebrow="Directory" title="Organizations" description="Review hospitals and clinics connected to the AiSteth network.">{canAdd&&<button className="button primary" onClick={()=>navigate("onboard-organization")}><Icon name="plus" size={15}/>Add organization</button>}</PageHeading><div className="toolbar"><div className="search-wrap"><Icon name="search" size={14}/><input className="search" value={query} onChange={e=>{setQuery(e.target.value);setPage(1)}} placeholder="Search all organization fields" aria-label="Search organizations"/></div><span className="updated">{visible.length} organizations</span></div><section className="card table-card organization-directory"><div className="table-scroll"><table><thead><tr><th>Code</th><th>Name</th><th>City</th><th>State</th><th>Country</th><th>Status</th><th className="numeric-cell">Professionals</th><th className="numeric-cell">Patients</th><th className="numeric-cell">Recordings</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{pageItems(visible,page).map((organization)=><tr key={organization.id}><td><span className="org-logo">{organization.code}</span></td><td className="organization-name">{organization.name}</td><td>{organization.city}</td><td>{organization.state}</td><td>{organization.country}</td><td><span className={`status ${organization.status==="Active"?"active":"review"}`}>{organization.status}</span></td><td className="numeric-cell">{organization.clinicians.toLocaleString()}</td><td className="numeric-cell">{organization.patients.toLocaleString()}</td><td className="numeric-cell">{organization.recordings.toLocaleString()}</td><td>{organization.created}</td><td><button type="button" className="table-action" onClick={()=>openOrg(organization)} aria-label={`View ${organization.name}`}>View <Icon name="chevron" size={11}/></button></td></tr>)}</tbody></table></div>{visible.length===0&&<div className="empty"><strong>No organizations found</strong>Try a different search term.</div>}<Pagination page={page} total={visible.length} onPageChange={setPage} label="Organizations"/></section></div>;
}

function Clinicians({clinicians,navigate,openClinician,canInvite}:{clinicians:Clinician[];navigate:(v:View)=>void;openClinician:(c:Clinician)=>void;canInvite:boolean}) {
  const [query,setQuery]=useState(""); const [page,setPage]=useState(1); const [subscription,setSubscription]=useState<"All"|Clinician["subscriptionStatus"]>("All");
  const visible=clinicians.filter(c=>(subscription==="All"||c.subscriptionStatus===subscription)&&`${c.name} ${c.specialty} ${c.organization}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="page"><PageHeading eyebrow="Provider network" title="Medical professionals" description="Providers grouped by their current subscription status.">{canInvite&&<button className="button primary" onClick={()=>navigate("onboard-clinician")}><Icon name="plus" size={15}/>Invite professional</button>}</PageHeading><div className="toolbar"><div className="search-wrap"><Icon name="search" size={14}/><input className="search" value={query} onChange={e=>{setQuery(e.target.value);setPage(1)}} placeholder="Search professionals"/></div><label className="status-filter"><span>Subscription</span><select value={subscription} onChange={(event)=>{setSubscription(event.target.value as "All"|Clinician["subscriptionStatus"]);setPage(1)}}><option>All</option><option>Active</option><option>Inactive</option><option>Expired</option></select></label><span className="updated">{visible.length} results</span></div><div className="provider-grid">{pageItems(visible,page).map(c=><article className="card provider-card" key={c.id} onClick={()=>openClinician(c)} style={{cursor:"pointer"}}><div className="provider-avatar">{initials(c.name)}</div><div><h3>{c.name}</h3><p>{c.specialty} · {c.role}</p><p>{c.organization}</p><span className={`pill subscription-${c.subscriptionStatus.toLowerCase()}`}>{c.subscriptionStatus}{c.subscriptionEndDate?` · until ${new Date(c.subscriptionEndDate).toLocaleDateString("en-IN")}`:""}</span></div></article>)}</div>{visible.length===0&&<div className="empty"><strong>No matching providers</strong>Change the search or subscription filter.</div>}<Pagination page={page} total={visible.length} onPageChange={setPage} label="Medical professionals"/></div>;
}

function useScopedMetrics(kind:"organization"|"provider",id:string){
  const [metrics,setMetrics]=useState<AnalyticsMetric[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const refresh=useCallback(async(range:ReportingRange)=>{setLoading(true);setError("");try{setMetrics(await getScopedDashboard(kind,id,range))}catch{setError("Scoped analytics are temporarily unavailable.")}finally{setLoading(false)}},[kind,id]);
  useEffect(()=>{const timer=window.setTimeout(()=>{void refresh(rangeForPeriod("All"))},0);return()=>window.clearTimeout(timer)},[refresh]);
  return {metrics,loading,error,refresh};
}

function OrganizationDetail({organization,clinicians,back,openClinician,setToast}:{organization:Organization;clinicians:Clinician[];back:()=>void;openClinician:(c:Clinician)=>void;setToast:(s:string)=>void}) {
  const [period,setPeriod]=useState("All");
  const [page,setPage]=useState(1);
  const {metrics,loading,error,refresh}=useScopedMetrics("organization",organization.id);
  const [range,setRange]=useState(rangeForPeriod("All"));
  const byKey=(key:string)=>metrics.find((metric)=>metric.key===key)?.value??"0";
  async function download(){try{await exportDashboardSummary([organization.id],range);setToast(`Summary emailed for ${organization.name}.`)}catch{setToast("The organization summary could not be delivered.")}}
  function changeRange(next:ReportingRange){setRange(next);void refresh(next)}
  return <div className="page"><PageHeading eyebrow="Organization overview" title={organization.name} description={`${organization.city}, ${organization.state} · Tenant-scoped connected analytics.`}><button className="button" onClick={back}>Back to directory</button><button className="button" onClick={()=>void download()}><Icon name="download" size={15}/>Download report</button></PageHeading><DateFilter period={period} setPeriod={setPeriod} onRangeChange={changeRange}/>{error&&<div className="notice" role="alert"><Icon name="info" size={16}/><span>{error}</span></div>}<section className="metrics"><DetailMetric label="Medical professionals" value={clinicians.length.toLocaleString("en-IN")} icon="stethoscope"/><DetailMetric label="Registered patients" value={loading?"—":byKey("patients")} icon="patient"/><DetailMetric label="Heart recordings" value={loading?"—":byKey("heart")} icon="heart"/><DetailMetric label="Lung recordings" value={loading?"—":byKey("lung")} icon="lungs"/></section><AnalyticsGrid metrics={metrics} scope={organization.name}/><section className="card table-card"><div className="card-head"><div><h3>Medical professionals for {organization.name}</h3><p>{clinicians.length} professionals currently returned for this organization</p></div></div>{clinicians.length?<div className="table-scroll"><table><thead><tr><th>Professional</th><th>Role</th><th>Specialty</th><th className="numeric-cell">Patients</th><th>Subscription</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{pageItems(clinicians,page).map(c=><tr key={c.id}><td><div className="org-cell"><span className="provider-avatar table-avatar">{initials(c.name)}</span><strong>{c.name}</strong></div></td><td>{c.role}</td><td>{c.specialty}</td><td className="numeric-cell">{c.patients.toLocaleString("en-IN")}</td><td><span className={`pill subscription-${c.subscriptionStatus.toLowerCase()}`}>{c.subscriptionStatus}</span></td><td><span className={`status ${c.status==="Active"?"active":"review"}`}>{c.status}</span></td><td><button type="button" className="table-action" onClick={()=>openClinician(c)} aria-label={`View ${c.name}`}>View <Icon name="chevron" size={11}/></button></td></tr>)}</tbody></table></div>:<div className="empty"><strong>No professionals returned</strong>The backend returned no professionals for this organization.</div>}<Pagination page={page} total={clinicians.length} onPageChange={setPage} label="Organization professionals"/></section></div>;
}

function DetailMetric({label,value,icon}:{label:string;value:string;icon:IconName}) { return <div className="metric"><div className="metric-main"><span className="metric-icon"><Icon name={icon} size={22}/></span><div><div className="metric-label">{label}</div><div className="metric-value">{value}</div></div></div><div className="metric-foot">Connected backend data</div></div>; }

function ClinicianDetail({clinician,organizations,back,onRenew}:{clinician:Clinician;organizations:Organization[];back:()=>void;onRenew:()=>void}) {
  const [period,setPeriod]=useState("All"); const [organization,setOrganization]=useState(clinician.organization);
  const {metrics,loading,error,refresh}=useScopedMetrics("provider",clinician.id);
  const byKey=(key:string)=>metrics.find((metric)=>metric.key===key)?.value??"0";
  return <div className="page"><PageHeading eyebrow="Professional overview" title={clinician.name} description={`${clinician.specialty} · ${organization}`}><button className="button" onClick={back}>Back to directory</button><button className="button primary" onClick={onRenew}>Renew subscription</button></PageHeading><div className="provider-filter"><DateFilter period={period} setPeriod={setPeriod} onRangeChange={(range)=>void refresh(range)}/><label className="organization-switcher">Associated organization<select value={organization} onChange={e=>setOrganization(e.target.value)}>{organizations.filter((item)=>item.name===clinician.organization).map(org=><option key={org.id}>{org.name}</option>)}</select></label></div>{error&&<div className="notice" role="alert"><Icon name="info" size={16}/><span>{error}</span></div>}<div className="notice"><Icon name="shield" size={16}/><span>Subscription: {clinician.subscriptionStatus}{clinician.subscriptionPlan?` · ${clinician.subscriptionPlan}`:""}{clinician.subscriptionEndDate?` · ends ${new Date(clinician.subscriptionEndDate).toLocaleDateString("en-IN")}`:""}</span></div><section className="metrics"><DetailMetric label="Assigned patients" value={loading?"—":byKey("patients")} icon="patient"/><DetailMetric label="Heart recordings" value={loading?"—":byKey("heart")} icon="heart"/><DetailMetric label="Lung recordings" value={loading?"—":byKey("lung")} icon="lungs"/><DetailMetric label="Lab reports" value={loading?"—":byKey("lab")} icon="report"/></section><AnalyticsGrid metrics={metrics} scope={clinician.name}/></div>;
}

function Locations({locations}:{locations:LocationView[]}) {
  const [page,setPage]=useState(1); const visible=pageItems(locations,page);
  const valid=locations.filter((item)=>Number.isFinite(item.latitude)&&Number.isFinite(item.longitude));
  const minLat=Math.min(...valid.map((item)=>item.latitude),0),maxLat=Math.max(...valid.map((item)=>item.latitude),1),minLon=Math.min(...valid.map((item)=>item.longitude),0),maxLon=Math.max(...valid.map((item)=>item.longitude),1);
  const latRange=maxLat-minLat||1,lonRange=maxLon-minLon||1;
  return <div className="page"><PageHeading eyebrow="Geographic view" title="Clinical network" description="Organization map and location directory from the connected backend."/><section className="network-map card" aria-label="Organization location map"><div className="map-grid"/>{valid.map((item)=><button key={item.organizationId} className="map-pin" style={{left:`${6+(item.longitude-minLon)/lonRange*88}%`,top:`${8+(maxLat-item.latitude)/latRange*78}%`}} title={`${item.organizationName} · ${item.city}, ${item.state} · ${item.providerCount} professionals`} aria-label={`${item.organizationName} in ${item.city}`}><Icon name="map" size={16}/><span>{item.organizationName}</span></button>)}</section><section className="card table-card"><div className="table-scroll"><table><thead><tr><th>Organization</th><th>City</th><th>State</th><th>Country</th><th>Professionals</th><th>Coordinates</th></tr></thead><tbody>{visible.map((item)=><tr key={item.organizationId}><td><div className="org-cell"><span className="org-logo">{initials(item.organizationName)}</span>{item.organizationName}</div></td><td>{item.city}</td><td>{item.state}</td><td>{item.country}</td><td>{item.providerCount.toLocaleString()}</td><td>{item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}</td></tr>)}</tbody></table></div>{locations.length===0&&<div className="empty"><strong>No locations returned</strong>The backend returned no organization locations.</div>}<Pagination page={page} total={locations.length} onPageChange={setPage} label="Organization locations"/></section></div>;
}

function OrganizationForm({disabled,onCreated,onToast}:{disabled:boolean;onCreated:(organization:Organization)=>void;onToast:(message:string)=>void}) {
  const [submitting,setSubmitting]=useState(false);
  const error="";
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSubmitting(true);
    const data=new FormData(event.currentTarget); const value=(name:string)=>String(data.get(name)??"").trim();
    try {
      const payload={name:value("name"),abdm_service_id:value("abdm_service_id"),address:value("address"),city:value("city"),state:value("state"),country:value("country"),pincode:value("pincode"),location:{latitude:Number(value("latitude")),longitude:Number(value("longitude"))}};
      const id=await createOrganization(payload);
      onCreated({id,name:payload.name,code:initials(payload.name),city:payload.city,state:payload.state,country:payload.country,created:new Date().toISOString().slice(0,10),status:"Active",clinicians:0,patients:0,recordings:0});
    } catch { onToast("Organization could not be created. Check the details and try again."); }
    finally { setSubmitting(false); }
  }
  return <div className="page"><PageHeading eyebrow="Management" title="Onboard organization" description="Create a clinic or hospital profile in the connected dashboard data store."/>{error&&<div className="notice" role="alert"><Icon name="info" size={16}/><span>{error}</span></div>}<form className="card form-card" onSubmit={submit}><div className="form-section"><div className="form-section-title"><h3>Organization identity</h3><p>Use the organization&apos;s legal or operating name.</p></div><div className="form-grid"><Field name="name" label="Clinic or hospital name" required/><Field name="abdm_service_id" label="ABDM service ID" required={false}/><Field name="address" label="Street address" full required/><Field name="city" label="City" required/><Field name="state" label="State or region" required/><Field name="country" label="Country" required/><Field name="pincode" label="Postal code" required/><Field name="latitude" type="number" label="Latitude" required step="any"/><Field name="longitude" type="number" label="Longitude" required step="any"/></div></div><div className="form-actions"><button type="reset" className="button" disabled={submitting}>Clear form</button><button type="submit" disabled={disabled||submitting} className="button primary">{disabled?"Insufficient permission":submitting?"Creating…":"Create organization"}</button></div></form></div>;
}

function ClinicianForm({organizations,disabled,onCreated,onToast}:{organizations:Organization[];disabled:boolean;onCreated:(clinician:Clinician)=>void;onToast:(message:string)=>void}) {
  const [submitting,setSubmitting]=useState(false);
  const error="";
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data=new FormData(event.currentTarget); const value=(name:string)=>String(data.get(name)??"").trim();
    const organization=organizations.find((item)=>item.name.toLocaleLowerCase()===value("organization").toLocaleLowerCase());
    if(!organization){onToast("Select an organization from the search results.");return;}
    setSubmitting(true);
    try {
      const email=value("email"); const phone=value("phone");
      const duration=Number(value("subscription"))===3?3:1; const name=value("name"); const specialty=value("specialty"); const role=value("role")==="Nurse"?"Nurse":"Doctor";
      const id=await createProvider({login:email,name,role,specialty,tenant_id:organization.id,address:value("address"),city:value("city"),state:value("state"),country:value("country"),pincode:value("pincode"),location:{latitude:Number(value("latitude")),longitude:Number(value("longitude"))},email:[{type:"WORK",value:email,is_primary:true}],phone:phone?[{type:"MOBILE",value:phone,is_primary:true}]:[],subscription_duration_years:duration});
      const subscriptionEnd=new Date(); subscriptionEnd.setFullYear(subscriptionEnd.getFullYear()+duration);
      onCreated({id,name,role,specialty,organization:organization.name,status:"Active",patients:0,subscriptionStatus:"Active",subscriptionPlan:duration===3?"3 Years Plan":"1 Years Plan",subscriptionEndDate:subscriptionEnd.toISOString()});
    } catch { onToast("The professional could not be invited. Check the details and try again."); }
    finally { setSubmitting(false); }
  }
  return <div className="page"><PageHeading eyebrow="Management" title="Invite medical professional" description="Create a provider under an organization and start their subscription."/>{error&&<div className="notice" role="alert"><Icon name="info" size={16}/><span>{error}</span></div>}<form className="card form-card" onSubmit={submit}><div className="form-section"><div className="form-section-title"><h3>Professional details</h3><p>Identity, organization, and subscription details.</p></div><div className="form-grid"><Field name="name" label="Doctor or nurse full name" required/><SelectField name="role" label="Professional role" required><option value="">Select a role</option><option>Doctor</option><option>Nurse</option></SelectField><Field name="specialty" label="Specialty or care area" required/><OrganizationSearchField organizations={organizations}/><Field name="email" type="email" label="Registration email" required/><Field name="phone" type="tel" label="Phone number" required={false}/><SelectField name="subscription" label="Initial subscription" required><option value="1">1 year</option><option value="3">3 years</option></SelectField></div></div><div className="form-section"><div className="form-section-title"><h3>Professional location</h3><p>Location fields required by the provider workflow.</p></div><div className="form-grid"><Field name="address" label="Street address" full required/><Field name="city" label="City" required/><Field name="state" label="State or region" required/><Field name="country" label="Country" required/><Field name="pincode" label="Postal code" required/><Field name="latitude" type="number" label="Latitude" required step="any"/><Field name="longitude" type="number" label="Longitude" required step="any"/></div></div><div className="form-actions"><button type="reset" className="button" disabled={submitting}>Clear form</button><button type="submit" disabled={disabled||submitting} className="button primary">{disabled?"Insufficient permission":submitting?"Inviting…":"Invite professional"}</button></div></form></div>;
}

function OrganizationSearchField({organizations}:{organizations:Organization[]}) {
  const [query,setQuery]=useState(""); const [open,setOpen]=useState(false); const [activeIndex,setActiveIndex]=useState(0);
  const debouncedQuery=useDebouncedValue(query,250);
  const results=useMemo(()=>{
    const term=debouncedQuery.trim().toLocaleLowerCase();
    if(term.length<2)return [];
    return organizations.filter((organization)=>`${organization.name} ${organization.city} ${organization.state}`.toLocaleLowerCase().includes(term)).slice(0,8);
  },[debouncedQuery,organizations]);
  function choose(organization:Organization){setQuery(organization.name);setOpen(false);}
  function keyDown(event:React.KeyboardEvent<HTMLInputElement>){
    if(event.key==="ArrowDown"){event.preventDefault();setOpen(true);setActiveIndex((index)=>Math.min(index+1,Math.max(0,results.length-1)));}
    else if(event.key==="ArrowUp"){event.preventDefault();setActiveIndex((index)=>Math.max(0,index-1));}
    else if(event.key==="Enter"&&open&&results[activeIndex]){event.preventDefault();choose(results[activeIndex]);}
    else if(event.key==="Escape")setOpen(false);
  }
  const showResults=open&&debouncedQuery.trim().length>=2;
  return <div className="form-field organization-combobox" onBlur={(event)=>{if(!event.currentTarget.contains(event.relatedTarget))setOpen(false)}}><label htmlFor="organization-search">Organization</label><div className="organization-search-control"><Icon name="search" size={15}/><input id="organization-search" name="organization" value={query} onChange={(event)=>{setQuery(event.target.value);setActiveIndex(0);setOpen(true)}} onFocus={()=>setOpen(true)} onKeyDown={keyDown} placeholder="Search tenant name" autoComplete="off" required role="combobox" aria-autocomplete="list" aria-expanded={showResults} aria-controls="organization-results"/><Icon className={`combobox-chevron ${showResults?"open":""}`} name="chevron" size={14}/></div>{showResults&&<div id="organization-results" className="organization-results" role="listbox">{results.length?results.map((organization,index)=><button key={organization.id} type="button" role="option" aria-selected={index===activeIndex} className={index===activeIndex?"active":""} onMouseDown={(event)=>event.preventDefault()} onClick={()=>choose(organization)}><span className="organization-result-mark">{organization.code}</span><span><strong>{organization.name}</strong><small>{organization.city}, {organization.state}</small></span><Icon name="chevron" size={13}/></button>):<div className="organization-no-results"><Icon name="search" size={16}/><span>No matching organizations</span></div>}</div>}<small>Type at least 2 characters. Results update after 250 ms.</small></div>;
}

function useDebouncedValue<T>(value:T,delay:number):T {
  const [debounced,setDebounced]=useState(value);
  useEffect(()=>{const timer=window.setTimeout(()=>setDebounced(value),delay);return()=>window.clearTimeout(timer)},[value,delay]);
  return debounced;
}

function Field({name,label,type="text",hint,error,full,required=false,step}:{name:string;label:string;type?:string;hint?:string|undefined;error?:string|undefined;full?:boolean;required?:boolean;step?:string}) { return <div className={`form-field ${full?"full":""}`}><label htmlFor={name}>{label}</label><input id={name} name={name} type={type} required={required} step={step} aria-invalid={!!error} aria-describedby={error?`${name}-error`:undefined}/>{error?<small className="error" id={`${name}-error`}>{error}</small>:hint&&<small>{hint}</small>}</div>; }
function SelectField({name,label,error,children,required=false}:{name:string;label:string;error?:string|undefined;children:ReactNode;required?:boolean}) { return <div className="form-field"><label htmlFor={name}>{label}</label><select id={name} name={name} required={required} aria-invalid={!!error}>{children}</select>{error&&<small className="error">{error}</small>}</div>; }

function ActivityLog() {
  return <div className="page"><PageHeading eyebrow="Governance" title="Activity log" description="Auditable administrative events from the connected backend."/><div className="notice"><Icon name="info" size={16}/><span>No activity endpoint is currently exposed by the connected backend, so no events are displayed.</span></div><section className="card"><div className="empty"><strong>No activity data available</strong>Connect an authorized audit-event endpoint to populate this view.</div></section></div>;
}
