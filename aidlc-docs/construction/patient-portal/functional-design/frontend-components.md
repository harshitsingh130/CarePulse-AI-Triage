# Frontend Components — Patient Portal

## Component Hierarchy

```
<App>
├── <AuthProvider>         (context: auth state, tokens, user info)
├── <WebSocketProvider>    (context: connection state, send/receive)
├── <Router>
│   ├── <LandingPage>
│   ├── <AuthPage>
│   │   ├── <PhoneEmailInput>
│   │   ├── <OTPInput>
│   │   └── <DOBInput>
│   ├── <ConsentPage>
│   │   └── <ConsentForm>
│   ├── <TriageChatPage>
│   │   ├── <ChatMessageList>
│   │   │   ├── <ChatBubble> (AI or Patient)
│   │   │   ├── <TypingIndicator>
│   │   │   └── <SeveritySlider>
│   │   ├── <ChatInput>
│   │   ├── <EmergencyBanner>
│   │   └── <NurseHandoffIndicator>
│   ├── <StatusPage>
│   │   ├── <ProgressStepper>
│   │   ├── <UrgencyBadge>
│   │   ├── <AppointmentCard>
│   │   └── <PatientSummaryCard>
│   ├── <AppointmentsPage>
│   │   ├── <AppointmentCard>
│   │   └── <EmptyState>
│   ├── <HistoryPage>
│   │   ├── <SessionCard>
│   │   └── <EmptyState>
│   └── <SettingsPage>
│       └── <ConsentManager>
├── <Navigation>           (top bar / bottom tabs)
├── <ToastContainer>       (notifications)
└── <ErrorBoundary>        (global error catch)
```

---

## Core Components

### ChatBubble

| Prop | Type | Description |
|---|---|---|
| role | "ai" \| "patient" \| "nurse" \| "system" | Who sent this message |
| content | string | Message text |
| timestamp | string | When sent |
| agentName | string? | Which AI agent (for nurse handoff transition) |

**Behavior**: Left-aligned for AI/nurse/system, right-aligned for patient. Different background colors per role.

---

### ChatInput

| Prop | Type | Description |
|---|---|---|
| onSend | (text: string) => void | Callback when user sends message |
| disabled | boolean | Disable during AI processing |
| placeholder | string | Input placeholder text |

**Behavior**: Text input + send button. Disabled while waiting for AI response. Enter key sends. Shift+Enter for newline.

---

### SeveritySlider

| Prop | Type | Description |
|---|---|---|
| onSelect | (value: number) => void | Callback with selected severity |
| visible | boolean | Only shown when AI asks for severity |

**Behavior**: Appears inline in chat when AI asks for severity rating. Horizontal 1-10 slider with color gradient. Selecting auto-sends.

---

### TypingIndicator

| Prop | Type | Description |
|---|---|---|
| visible | boolean | Show/hide |
| actor | "ai" \| "nurse" | Who is typing |

**Behavior**: Three animated dots in an AI-style bubble. Shows while waiting for AI/nurse response.

---

### EmergencyBanner

| Prop | Type | Description |
|---|---|---|
| visible | boolean | Show when Emergency detected |
| onConnect | () => void | Live transfer callback |
| onDismiss | () => void | Patient declines transfer |

**Behavior**: Full-width red banner at top of chat. Persistent until dismissed or session ends.

---

### ProgressStepper

| Prop | Type | Description |
|---|---|---|
| currentStep | number | Active step (0-indexed) |
| steps | Step[] | Array of {label, completed, active} |

**Steps**: Assessment → Scoring → Routing → Appointment → Complete

---

### UrgencyBadge

| Prop | Type | Description |
|---|---|---|
| level | "EMERGENCY" \| "URGENT" \| "STANDARD" \| "ROUTINE" | Urgency |

**Colors**: Emergency=red, Urgent=orange, Standard=blue, Routine=green

---

### AppointmentCard

| Prop | Type | Description |
|---|---|---|
| department | string | Specialist department |
| specialist | string? | Doctor name |
| datetime | string | ISO datetime |
| clinic | string | Clinic name |
| preparation | string? | Prep instructions |

---

### ConsentForm

| Prop | Type | Description |
|---|---|---|
| onSubmit | (consents: string[]) => void | Callback with granted consent types |

**Behavior**: Three checkboxes (all required). Submit disabled until all checked. "Learn more" expandable per type.

---

### OTPInput

| Prop | Type | Description |
|---|---|---|
| length | number | Number of digits (6) |
| onComplete | (code: string) => void | Callback when all digits entered |

**Behavior**: 6 individual digit inputs. Auto-advance on entry. Paste support (paste full code). Auto-submit when 6th digit entered.

---

## State Management

### Global State (React Context)

```typescript
interface AuthState {
  isAuthenticated: boolean;
  patientId: string | null;
  tokens: { idToken: string; accessToken: string; refreshToken: string } | null;
  hasConsent: boolean;
}

interface WebSocketState {
  connected: boolean;
  connectionId: string | null;
  reconnecting: boolean;
  reconnectAttempt: number;
}

interface TriageState {
  activeSessionId: string | null;
  status: SessionStatus;
  messages: ChatMessage[];
  urgencyResult: UrgencyResult | null;
  routingDecision: RoutingDecision | null;
}
```

### Per-Page State (Local)
- Form inputs (controlled components)
- Loading states
- Error states
- Polling timers

---

## API Integration

### REST API Calls

| Hook | Endpoint | When |
|---|---|---|
| `useTriageStatus(sessionId)` | GET /triage/status/{id} | Status page, polling every 5s |
| `useTriageHistory()` | GET /triage/history | History page load |
| `useAppointments()` | GET /appointments | Appointments page load |
| `useConsent()` | GET /profile (consent field) | App init |
| `grantConsent(types)` | POST /consent | Consent page submit |
| `revokeConsent(type)` | DELETE /consent/{type} | Settings page |

### WebSocket Messages

| Direction | Event | Payload |
|---|---|---|
| Client → Server | sendMessage | `{ action: "sendMessage", data: { text: "..." } }` |
| Server → Client | aiResponse | `{ type: "message", role: "ai", content: "..." }` |
| Server → Client | nurseResponse | `{ type: "message", role: "nurse", content: "..." }` |
| Server → Client | statusUpdate | `{ type: "status", status: "..." }` |
| Server → Client | emergencyAlert | `{ type: "emergency", offer_transfer: true }` |
| Server → Client | sessionComplete | `{ type: "complete", summary: {...} }` |
| Server → Client | severityRequest | `{ type: "ui_component", component: "severity_slider" }` |

---

## Form Validation

### Auth Page

| Field | Validation | Error Message |
|---|---|---|
| Phone | Matches E.164 format or 10-digit US | "Enter a valid phone number" |
| Email | Valid email format | "Enter a valid email address" |
| OTP | Exactly 6 digits | "Enter the 6-digit code" |
| DOB | Valid date, not in future, age 0-120 | "Enter a valid date of birth" |

### Chat Input

| Rule | Validation |
|---|---|
| Not empty | Cannot send empty message |
| Max length | 1000 characters |
| No HTML/script | Strip HTML tags before sending |
