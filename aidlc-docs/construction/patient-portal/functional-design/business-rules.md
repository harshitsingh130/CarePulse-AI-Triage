# Business Rules — Patient Portal

## BR-PP-001: Authentication Required for PHI

**Rule**: Any page that displays or collects PHI requires authentication. Pages that show only generic information do not.

| Page | Auth Required | Rationale |
|---|---|---|
| Landing | No | Generic — no patient data |
| Auth | No | This IS the auth flow |
| Consent | Yes | Records consent against patient identity |
| Triage Chat | Yes | Collects and displays PHI (symptoms) |
| Status | Yes | Displays triage results (PHI) |
| Appointments | Yes | Patient-specific scheduling data |
| History | Yes | Past triage records (PHI) |
| Settings | Yes | Consent management |

**Emergency exception**: If patient is in active Emergency escalation and auth token expires mid-chat, do NOT interrupt the chat. Silently attempt token refresh. If refresh fails, continue the chat session (Step Functions has its own auth) — re-authenticate for Portal pages later.

---

## BR-PP-002: Token Security

**Rule**: Authentication tokens are handled securely:

| Token | Storage | Lifetime |
|---|---|---|
| ID Token | Memory (JavaScript variable) | 1 hour |
| Access Token | Memory (JavaScript variable) | 1 hour |
| Refresh Token | sessionStorage (encrypted) | 30 days |

- **Never** store tokens in localStorage (persists across sessions, XSS-vulnerable)
- **Never** include tokens in URLs (logged in server access logs)
- Tokens attached to requests via `Authorization: Bearer` header
- On tab close: tokens cleared from memory (sessionStorage persists for tab refresh only)

---

## BR-PP-003: WebSocket Reconnection

**Rule**: If the WebSocket connection drops during active chat:

| Attempt | Wait | Behavior |
|---|---|---|
| 1 | 1 second | Silent reconnect attempt |
| 2 | 3 seconds | Show "Reconnecting..." indicator |
| 3 | 5 seconds | Show "Connection lost" with manual retry button |
| Failed all | — | "Unable to connect. Your session is saved — you can return later." |

On successful reconnect:
- Re-associate connection with active session
- Load any messages received while disconnected (GET from chat history API)
- Resume chat seamlessly

---

## BR-PP-004: No PHI in Client Logs

**Rule**: The frontend MUST NOT log PHI to the browser console or any client-side logging service.

**Allowed to log**: API errors (without response body), WebSocket connection status, navigation events, performance metrics
**Forbidden to log**: Patient messages, symptom data, medication lists, appointment details, session contents

---

## BR-PP-005: Responsive Breakpoints

**Rule**: The portal MUST work at these breakpoints:

| Breakpoint | Device | Layout |
|---|---|---|
| 375px | Mobile (iPhone SE) | Single column, bottom tab nav, full-width chat |
| 768px | Tablet (iPad) | Two-column where appropriate, top nav |
| 1280px | Desktop | Max-width container (1024px), sidebar nav optional |

**Chat specifically**:
- Mobile: full-screen chat (no side panels)
- Tablet: chat centered, max-width 600px
- Desktop: chat centered, max-width 700px, with status sidebar

---

## BR-PP-006: Real-Time Status Updates

**Rule**: Triage status page updates in near-real-time without manual refresh.

**Implementation**: Poll `GET /triage/status/{sessionId}` every 5 seconds while status is not COMPLETED.

| Status | UI Update |
|---|---|
| IN_PROGRESS | Progress stepper: "Assessment in progress..." |
| AWAITING_NURSE | "A nurse is reviewing your case" |
| AWAITING_ROUTING | "Finding the right specialist for you..." |
| SCHEDULED | Show appointment details card |
| COMPLETED | Full result card + "What's next" guidance |
| ESCALATED | Red banner: "Emergency — medical staff has been notified" |

Stop polling once status is COMPLETED or ESCALATED (terminal states).

---

## BR-PP-007: Consent Must Be Collected Before Triage

**Rule**: If patient has no consent on record, they CANNOT start triage. They are redirected to /consent.

**Flow**:
```
Patient clicks "Start Triage"
  → Check: has consent? (from auth token claims or API call)
  → If no consent: redirect to /consent
  → If consent granted: proceed to /triage
```

---

## BR-PP-008: Severity Slider UX

**Rule**: When the AI asks "On a scale of 1-10, how severe is it?", the chat UI shows a visual slider component (not just a text input).

**Slider design**:
- Horizontal scale 1-10 with color gradient (green → yellow → red)
- Labels: 1="Barely noticeable" 5="Moderate" 10="Worst imaginable"
- Large touch target (44px handle)
- Selecting a number auto-sends it as the patient's response
- Patient can also type a number in the text input instead

---

## BR-PP-009: Emergency State Takes Over

**Rule**: If Emergency is detected during chat:

1. Chat messages continue (don't interrupt)
2. Red banner appears at top: "Based on your symptoms, we're alerting medical staff."
3. "Connect to medical staff now" button appears (prominent, pulsing)
4. If patient clicks connect: initiate live transfer (WebSocket routing to physician)
5. If patient declines: show "Help is on the way. If symptoms worsen, call 911."
6. Status page immediately reflects ESCALATED state

---

## BR-PP-010: Offline / Slow Connection Handling

**Rule**: The portal degrades gracefully on poor connections:

| Scenario | Behavior |
|---|---|
| API call takes > 3 seconds | Show loading skeleton, keep trying |
| API call fails | Toast: "Something went wrong" + retry button |
| WebSocket won't connect | "Chat unavailable — please try again or call [clinic phone]" |
| Page loads but API is down | Show cached data (if available from sessionStorage) with "Last updated [time]" badge |

---

## BR-PP-011: Session Resumption UX

**Rule**: If patient returns to the portal with an IN_PROGRESS session:

- Landing page shows: "You have an incomplete triage. Resume?" with two buttons:
  - "Resume" → navigate to /triage (conversation picks up where it left off)
  - "Start Fresh" → mark old session as ABANDONED, create new one

---

## BR-PP-012: Accessibility (WCAG 2.1 AA)

**Rule**: The portal MUST meet WCAG 2.1 AA. Specifically for healthcare:

- **Color contrast**: 4.5:1 minimum (critical for older patients)
- **Touch targets**: 44px minimum (arthritic hands, motor impairment)
- **Font size**: Base 16px, never smaller than 14px
- **Screen reader**: All dynamic content announces via ARIA live regions (chat messages, status changes)
- **Keyboard**: Full keyboard navigation, visible focus indicators
- **Reduced motion**: Respect `prefers-reduced-motion` (disable animations, typing indicators become static "...")
- **High contrast mode**: System high contrast support (forced-colors media query)
