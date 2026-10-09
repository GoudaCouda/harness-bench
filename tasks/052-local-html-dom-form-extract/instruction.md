# Appointment hold handoff

Act as a personal scheduling assistant. Read `/workspace/user_request.md`, then use the live local appointment service at `$MOCK_SITE_BASE` to complete the request.

The service is the authority for availability and appointment details. Start at its index page, preserve its session cookie and hidden form values, inspect the returned candidates and detail pages, and use the site's hold workflow. Do not use the public internet or invent a slot from the request.

The portal uses a self-contained scenario clock so the task remains reproducible on any date. Treat the status and expiry shown by the service as authoritative; do not compare them with the host computer's current date.

The user authorizes **one temporary hold request only**. Submit the hold form at most once; a second hold request is outside scope even if the first request was rejected. Do not confirm an appointment, submit payment, or place a backup hold. If the site shows an earlier option that violates any stated constraint, do not select it. A hold is not a confirmed booking.

After verifying the hold receipt, create exactly these two files in `/workspace`:

- `appointment_summary.md`: a concise handoff stating the temporary status, hold code, hold expiry, selected service, office and full address, appointment date/time/time zone, why this is the earliest feasible option, required preparation/documents, and the fact that confirmation/payment were not performed.
- `appointment.ics`: one valid calendar event for the held appointment. It must use the service's appointment start/end and time zone, include the office address, identify the hold code and hold expiry in the UID/description, and mark the event tentative rather than confirmed.

Do not write cookies, CSRF values, hold tokens, copied HTML, screenshots, request traces, source-URL lists, or any additional workspace files. Temporary browsing artifacts belong in `/tmp` or `/runtime`.
