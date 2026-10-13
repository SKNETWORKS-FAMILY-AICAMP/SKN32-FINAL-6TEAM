export type IncidentStatus = "new" | "investigating" | "resolved";
export type IncidentSeverity = "high" | "medium" | "low";
export type IncidentSource = "server" | "web" | "job";

export const INCIDENT_STATUS: Record<IncidentStatus, string> = { new: "확인 전", investigating: "조사 중", resolved: "해결" };
export const INCIDENT_SEVERITY: Record<IncidentSeverity, string> = { high: "높음", medium: "보통", low: "낮음" };
export const INCIDENT_SOURCE: Record<IncidentSource, string> = { server: "서버", web: "웹", job: "상시 작업" };

export interface IncidentOccurrence {
  reference: string;
  occurredAt: string;
  traceId: string;
  userHash: string | null;
  tripId: string | null;
  caseId: string | null;
  source: IncidentSource;
}

export interface ManagementIncident {
  id: string;
  code: string;
  title: string;
  module: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  source: IncidentSource;
  affectedUsers: number | null;
  firstSeen: string;
  lastSeen: string;
  hourlyCounts: number[];
  occurrences: IncidentOccurrence[];
  hint?: string;
  maskedStack?: string;
}

export interface ManagementSnapshot {
  source: "demo";
  asOf: string;
  incidents: ManagementIncident[];
}

export interface ManagementGateway {
  getSnapshot(): Promise<ManagementSnapshot>;
}

export interface IncidentFilters {
  query: string;
  status: string;
  severity: string;
  source: string;
}

export function incidentEventCount(incident: ManagementIncident): number {
  return incident.hourlyCounts.reduce((total, count) => total + count, 0);
}

export function incidentSources(incident: ManagementIncident): IncidentSource[] {
  return [...new Set([incident.source, ...incident.occurrences.map(event => event.source)])];
}

export function filterIncidents(incidents: ManagementIncident[], filters: IncidentFilters): ManagementIncident[] {
  const query = filters.query.trim().toLocaleLowerCase();
  return incidents.filter(incident =>
    (!filters.status || incident.status === filters.status) &&
    (!filters.severity || incident.severity === filters.severity) &&
    (!filters.source || incidentSources(incident).some(source => source === filters.source)) &&
    (!query || [incident.code, incident.title, ...incident.occurrences.flatMap(event => [event.reference, event.traceId])]
      .some(value => value.toLocaleLowerCase().includes(query))),
  );
}
