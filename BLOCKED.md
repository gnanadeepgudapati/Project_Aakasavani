# BLOCKED

Things needed from the user. In autonomous mode this file replaces asking.

**Newest first. Resolved items move to the bottom under RESOLVED with a date.**

---

## OPEN

### B-003 · Deployment Python version — install 3.14 on the VPS, or pin to 3.12 there?

**Raised:** 2026-08-09
**Blocks:** nothing in steps 01–21. Deployment only.
**Needed from user:** A or B, whenever deployment planning starts — not now.

Residual of B-001. Dev now runs 3.14 (`CLAUDE.md` § Stack, `logs/SESSIONS.md`
S-005). Ubuntu 24.04's system Python is 3.12.

| Option | Notes |
|---|---|
| **A. Install 3.14 on the VPS** (deadsnakes PPA or pyenv) | Matches dev exactly. A few extra minutes of server setup |
| **B. Pin the deploy venv to 3.12** | Uses the system Python as-is. Re-verify the wheel stack on 3.12 before relying on it — not yet tested, only 3.14 has been |

No recommendation yet — low stakes, revisit near step 22 (deployment).

---

### B-002 · Credentials required before their build steps

**Raised:** 2026-08-08, planning session
**Blocks:** 01 (partially), 11, 14, 15–17, 20
**Needed from user:** the values below, in a `.env` file at repo root

| Variable | Needed for | Step | Free? | Where to get it |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | Research panel — the only LLM in the system | 14–17 | No, ~$5–6/mo | `console.anthropic.com` |
| `IA_S3_ACCESS_KEY` | Internet Archive Save Page Now | 11 | Yes | `archive.org/account/s3.php` |
| `IA_S3_SECRET_KEY` | ditto | 11 | Yes | ditto |
| `GUARDIAN_API_KEY` | Deep history, Guardian Open Platform | 20 | Yes, 5k/day | `open-platform.theguardian.com/access` |
| `AAKASAVANI_PASSWORD` | Caddy HTTP basic auth | deploy | — | Choose one |

**None of these block steps 02–09** — the product ships without any of them.
Only `ANTHROPIC_API_KEY` is a paid service, and it is not needed until step 14.

**Note on step 01:** the feed audit itself needs no credentials. It is listed
above only because a `.env.example` should be committed alongside it.

---

## RESOLVED

### B-001 · Python version — spec said 3.12, machine has 3.14.3 and 3.13

**Raised:** 2026-08-08 · **Resolved:** 2026-08-09, by measurement, approved as
part of plan approval.

Original worry: `CLAUDE.md` pinned 3.12; only 3.14.3/3.13 are installed, and
`lxml` (via Trafilatura) is a compiled dependency that could lack a 3.14 wheel
and fall back to a source build requiring MSVC. **Tested instead of assumed:**

```
python 3.14.3 | lxml 6.1.1 | trafilatura 2.2.0
              | feedparser 6.0.14 | fastapi 0.141.1

content:encoded extracted        OK
absent content -> getattr None   OK
malformed XML survived (bozo=1)  OK, 1 entry, no crash
extraction with images           OK, 803 chars, <img> preserved
paywall stub -> 18 chars         OK, correctly <500 = failure
```

Whole stack installs from binary wheels and runs. 3.14 has been out long enough
that the ecosystem caught up; the original wheel-availability concern was
stale. `CLAUDE.md` § Stack now records 3.14 for dev (`logs/SESSIONS.md` S-005).
Residual deployment-only question tracked separately as **B-003**.
