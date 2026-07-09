/**
 * TypeScript interfaces for the Patient Portal.
 * Mirrors the Python Pydantic models for frontend consumption.
 */

export type UrgencyLevel = 'EMERGENCY' | 'URGENT' | 'STANDARD' | 'ROUTINE';
export type SessionStatus = 'IN_PROGRESS' | 'AWAITING_NURSE' | 'AWAITING_ROUTING' | 'SCHEDULED' | 'COMPLETED' | 'ESCALATED' | 'PAUSED';

export interface PatientSummary {
  symptoms_reported: string;
  medications_reviewed: string;
  urgency_level: string;
  next_steps: string;
}

export interface AppointmentSlot {
  datetime: string;
  specialist_name: string;
  duration_minutes: number;
}

export interface Appointment {
  patientId: string;
  appointmentId: string;
  sessionId: string;
  department: string;
  specialistName?: string;
  clinicId: string;
  clinicName?: string;
  scheduledAt: string;
  status: 'SCHEDULED' | 'CONFIRMED' | 'CANCELLED' | 'COMPLETED';
  preparationNotes?: string;
}

export interface TriageStatusResponse {
  session_id: string;
  status: SessionStatus;
  urgency_level?: UrgencyLevel;
  department?: string;
  routing_reasoning?: string;
  urgency_reasoning?: string;
  urgency_confidence?: number;
  recommended_timeframe?: string;
  primary_complaint?: string;
  patient_summary?: PatientSummary;
  appointment?: Appointment;
  started_at: string;
  completed_at?: string;
}

export interface TriageHistoryItem {
  session_id: string;
  primary_complaint: string;
  urgency_level: UrgencyLevel;
  department?: string;
  status: SessionStatus;
  started_at: string;
  completed_at?: string;
}

export interface ChatMessage {
  id: string;
  role: 'ai' | 'patient' | 'nurse' | 'system';
  content: string;
  timestamp: string;
  showSeveritySlider?: boolean;
  emergencyAlert?: boolean;
}

export interface WebSocketMessage {
  type: 'message' | 'status' | 'emergency' | 'complete' | 'ui_component';
  role?: 'ai' | 'nurse';
  content?: string;
  status?: SessionStatus;
  component?: string;
  offer_transfer?: boolean;
  summary?: PatientSummary;
  urgency_level?: UrgencyLevel;
  department?: string;
}

export interface ConsentStatus {
  dataProcessing: boolean;
  aiTriage: boolean;
  dataSharing: boolean;
}

export interface AuthState {
  isAuthenticated: boolean;
  patientId: string | null;
  accessToken: string | null;
  hasConsent: boolean;
}
