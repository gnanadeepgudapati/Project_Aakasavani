# BLOCKED

Things needed from the user. In autonomous mode this file replaces asking.

**Newest first. Resolved items move to the bottom under RESOLVED with a date.**

---

## OPEN

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

### B-001 · Python version — spec says 3.12, machine has 3.14.3 and 3.13

**Raised:** 2026-08-08, planning session
**Blocks:** 01, and therefore everything
**Status:** needs a decision before any code runs

`CLAUDE.md` § Stack pins **Python 3.12**. `py --list` reports only:

```
 -V:3.14 *        Python 3.14 (64-bit)     ← default
 -V:3.13          Python 3.13 (64-bit)
```

3.12 is not installed. `CLAUDE.md` says the stack may be challenged in planning
but **not changed silently mid-build**, so this is raised now rather than
resolved unilaterally.

**Why it matters:** the risk is not the language, it is the C-extension wheels.
`lxml` (via Trafilatura) and the `charset-normalizer` / `cchardet` family are
compiled. A version with no prebuilt wheel falls back to building from source,
which on Windows needs a MSVC toolchain and usually fails.

**The three options:**

| Option | Cost | Risk |
|---|---|---|
| **A. Install Python 3.12** | ~5 min download | **None.** Matches the spec exactly. Known-good wheels for every dependency |
| **B. Use 3.13** | Free | Low. 3.13 has been out long enough that Trafilatura/lxml wheels exist |
| **C. Use 3.14** | Free | Moderate. Newest release; wheel coverage is the thinnest and `pip` may try to compile |

**My recommendation: A — install 3.12.** It is the only option with zero
uncertainty, the spec already says 3.12, and this is a deployment target
(Ubuntu 24.04 VPS) where 3.12 is the system Python. Matching dev to prod is
worth five minutes.

If the user prefers not to install anything, **B (3.13)** is the fallback and
`CLAUDE.md` must be patched in the same commit, per the SESSIONS rule.

**Decision needed:** A, B, or C.

---

## RESOLVED

*(none yet)*
