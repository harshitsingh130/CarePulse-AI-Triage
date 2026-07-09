# Business Logic Model — Patient Portal (Unit 8)

## Overview

The Patient Portal is the patient-facing web/mobile-responsive React application. It handles authentication, consent collection, the real-time triage chat interface, triage status display, appointment viewing, and session history. It connects to the backend via REST API (status, appointments, consent) and WebSocket API (live chat).

---

## Page Architecture

```
/                          → Landing / Start Triage
/auth                      → Authentication (SMS/email + DOB)
/consent                   → Consent collection (first-time only)
/triage                    → Active triage chat
/triage/:sessionId/status  → Triage result + status
/appointments              → Upcoming appointments
/history                   → Past triage sessions
/settings                  → Consent management
```

---

## Page 1: Landing / Start Triage

**Purpose**: Entry point. Patient decides to start a new triage.

**UI Elements**:
- Hero message: "Get help with your symptoms — available 24/7"
- "Start Triage" primary CTA button
- "View My Appointments" secondary link (requires auth)
- "Already have an account? Sign in" link

**Logic**:
- If patient is already authenticated (valid token in storage) → skip auth
- If patient has active IN_PROGRESS session → redirect to `/triage` with resume prompt
- If patient has no consent on file → redirect to `/consent` after auth

---

## Page 2: Authentication

**Purpose**: Verify patient identity via SMS/email + DOB.

**Flow**:
```
Step 1: Patient enters phone OR email
         |
         v
Step 2: System sends OTP (6-digit code)
        Patient sees: "We sent a code to [phone/email]"
         |
         v
Step 3: Patient enters OTP code
        [If wrong → "Invalid code. X attempts remaining."]
        [If correct → proceed]
         |
         v
Step 4: Patient enters date of birth
        [If wrong → "DOB doesn't match our records. Try again."]
        [If correct → authenticated, tokens stored]
         |
         v
Redirect to /consent (first time) or /triage (returning)
```

**UI Elements**:
- Phone/email input with toggle ("Use phone" / "Use email")
- OTP input (6 separate digit boxes, auto-advance)
- DOB input (date picker or MM/DD/YYYY format)
- "Resend code" link (available after 30s)
- Error messages (inline, not modal)
- Loading spinner on submit

**Business Rules**:
- OTP expires after 10 minutes
- Max 5 failed attempts → account temporarily locked (15 minutes)
- DOB check: exact match against Patient.dateOfBirth in DynamoDB
- Tokens stored in memory (not localStorage) for security — sessionStorage only for refresh token

---

## Page 3: Consent Collection

**Purpose**: Collect required consent before first triage.

**Shown**: Only on first visit (before any consent is on file).

**UI Elements**:
- Clear explanation of each consent type:
  - ✅ "I consent to AI-assisted assessment of my symptoms" (required)
  - ✅ "I consent to processing my health data for triage" (required)
  - ✅ "I consent to sharing my information with the assigned specialist" (required)
- "All three are required to use the triage service"
- "Grant Consent" primary button (disabled until all checked)
- "Learn more" expandable sections with detailed explanations
- "What if I don't consent?" link → explains they can call the clinic instead

**Logic**:
- All three consent types required → POST /consent with array
- On success → redirect to /triage
- Timestamp recorded for each consent grant

---

## Page 4: Triage Chat (Core Experience)

**Purpose**: Real-time conversational interface with the AI triage agent.

**UI Layout**:
```
+------------------------------------------+
|  Healthcare Network - Triage Chat    [X] |
+------------------------------------------+
|                                          |
|  [AI bubble] Hi, I'm here to help       |
|  assess your symptoms. What's your       |
|  main concern today?                     |
|                                          |
|              [Patient bubble] I've had   |
|              a bad headache for 3 days   |
|                                          |
|  [AI bubble] I'm sorry to hear that.    |
|  On a scale of 1-10...                  |
|                                          |
|  [typing indicator...]                   |
|                                          |
+------------------------------------------+
|  [text input]              [Send button] |
+------------------------------------------+
```

**UI Elements**:
- Chat message list (scrollable, newest at bottom)
- AI messages: left-aligned, branded color bubble
- Patient messages: right-aligned, neutral bubble
- Typing indicator (animated dots) while AI processes
- Text input with send button
- "Thinking..." state when AI is generating response
- Severity selector (1-10 visual slider) when AI asks for severity
- Emergency banner (red, full-width) if Emergency classification mid-chat

**WebSocket Integration**:
- On page load: connect to WebSocket API with JWT in query string
- On connect success: start triage (or resume existing session)
- On `sendMessage`: send patient text to WebSocket
- On receive: append AI message to chat, hide typing indicator
- On disconnect: show "Connection lost. Reconnecting..." with auto-retry (3 attempts, exponential backoff)

**Special States**:
- **Nurse handoff**: Chat continues seamlessly. Show subtle indicator: "A nurse is now reviewing your case" (small badge, not alarming)
- **Emergency detected**: Red banner: "Based on your symptoms, we're connecting you with medical staff immediately." + "Connect now" button for live transfer
- **Session complete**: Chat fades, "Your triage is complete" card appears with urgency level + next steps + link to /status

---

## Page 5: Triage Status

**Purpose**: Show triage results and real-time status updates.

**UI Elements**:
- Status card with urgency badge (color-coded: red/orange/blue/green)
- Progress stepper: Assessment ✓ → Scoring ✓ → Routing ✓ → Appointment ✓
- Urgency result: "[Level] — [recommended timeframe]"
- Department assigned: "[Department name]"
- Appointment details (if scheduled): date, time, clinic, specialist
- "View SOAP Summary" button → shows PatientSummary (redacted, not full SOAP)
- "Start New Triage" button (for follow-up issues)

**Real-time updates**:
- Subscribe to session status via polling (GET /triage/status/{id} every 5 seconds while IN_PROGRESS)
- When status changes → update progress stepper + show new info
- When COMPLETED → show full result card

---

## Page 6: Appointments

**Purpose**: View upcoming and past appointments.

**UI Elements**:
- Card list of upcoming appointments:
  - Department + specialist name
  - Date + time
  - Clinic name + address
  - "Preparation notes" (if any)
  - Calendar icon with "Add to Calendar" (iCal download)
- Past appointments section (collapsed by default)
- Empty state: "No upcoming appointments" + "Start a triage to get scheduled"

---

## Page 7: History

**Purpose**: View past triage sessions.

**UI Elements**:
- List of past sessions (card per session):
  - Date
  - Primary complaint (brief)
  - Urgency level (badge)
  - Outcome (department routed, appointment date)
- Click to expand: view PatientSummary for that session
- Sorted: most recent first

---

## Page 8: Settings (Consent Management)

**Purpose**: View and manage consent preferences.

**UI Elements**:
- Current consent status (granted/not granted) per type
- Toggle to revoke each consent type
- Warning on revocation: "Revoking consent will prevent you from using the triage service. You can still call the clinic directly."
- Confirm dialog on revocation: "Are you sure? This takes effect within 24 hours."
- "Last updated: [date]" per consent

---

## Application-Wide Components

### Navigation
- Top bar: Logo + "Start Triage" + "Appointments" + "History" + avatar/settings
- Mobile: bottom tab bar (Triage | Appointments | History | Settings)
- Show active indicator on current page

### Authentication Guard
- All pages except Landing require authentication
- If token expired → redirect to /auth with return URL
- Refresh token flow: silent refresh in background, no UX interruption

### Error Handling
- API errors: toast notification (top-right, auto-dismiss 5s)
- Network errors: persistent banner "Connection issue — retrying..."
- 401 errors: redirect to /auth
- 500 errors: "Something went wrong. Please try again." + retry button

### Loading States
- Skeleton loaders on all pages (shimmer animation, not spinners)
- Chat: typing indicator for AI responses
- Forms: button loading state (spinner inside button, disabled)

### Accessibility
- All interactive elements keyboard navigable
- ARIA labels on icon buttons
- Skip-to-content link
- High contrast mode support (large touch targets: 44px minimum)
- Focus rings on keyboard navigation (`:focus-visible` only)
- `prefers-reduced-motion` respected (no animations)
