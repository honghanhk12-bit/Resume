# Job Hunt Orchestration Agents

A four-agent pipeline that takes a target job title, location, and your resume,
finds real job listings, and produces ATS-optimised, tailored resume `.docx`
files.

## How it works

```
                 ┌──────────┐
 job listings →  │  Scout   │ → ScoutReport (keywords, skills, phrases, red flags)
                 └────┬─────┘
                      ▼
                 ┌──────────┐
 your resume  →  │Strategist│ → StrategyReport (ATS score, gaps, section order)
                 └────┬─────┘
                      ▼
                 ┌──────────┐
                 │ Surgeon  │ → RewrittenResume (XYZ-format bullets, keywords embedded)
                 └────┬─────┘
                      ▼
                 ┌──────────┐
                 │ Auditor  │ → AuditReport (pass/fail, issues to fix)
                 └────┬─────┘
                      ▼
           (loop back to Surgeon up to 2x if not approved)
                      ▼
              outputs/*.docx
```

1. **Scout** — searches for up to `MAX_LISTINGS_TO_FETCH` live job listings
   (default 5, via the Serper.dev Google Jobs API) and extracts the
   recurring keywords, required/preferred skills, repeated phrasing,
   seniority signals, and ATS red flags across them.
2. **Strategist** — scores your current resume against that market signal
   (0-100), finds gaps and strengths, and recommends a section order.
3. **Surgeon** — rewrites every bullet in Google's XYZ format
   (`Accomplished [X], measured by [Y], by doing [Z]`), embedding keywords
   naturally without fabricating metrics.
4. **Auditor** — runs a final ATS compliance check (keyword coverage, XYZ
   compliance, readability, quantification rate, section completeness) and
   either approves the resume or sends it back to the Surgeon (up to 2 retries).

The approved resume is written out as a clean, single-column `.docx` file
with no tables, columns, text boxes, or special characters — the formatting
ATS parsers choke on.

## Setup

1. **Install dependencies** (Python 3.10+ recommended):

   ```bash
   cd job_hunt_agents
   pip install -r requirements.txt
   ```

2. **Get API keys**:
   - Anthropic API key: https://console.anthropic.com/settings/keys
   - Serper API key (free tier available): https://serper.dev

3. **Set your API keys** as environment variables (preferred):

   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   export SERPER_API_KEY="..."
   ```

   ...or fill them directly into `config.py`.

4. **Configure your target role** in `config.py`:

   ```python
   TARGET_ROLE = "Head of Data"
   TARGET_LOCATION = "London"
   TARGET_INDUSTRY = "Real Estate"
   ```

5. **Drop your resume** (PDF or DOCX) at `data/resume.pdf` (or point
   `RESUME_PATH` / `--resume` at a different file).

## Usage

### Single tailored resume (aggregate market signal)

Fetches up to `MAX_LISTINGS_TO_FETCH` listings (default 5), builds one
market-signal report, and produces one tailored resume optimised for that
overall role/market:

```bash
python main.py
```

Override any config value from the CLI:

```bash
python main.py --role "Head of Data" --location "London" --industry "Real Estate" --max-listings 50
```

### Batch mode — one tailored resume per job listing

```bash
python main.py --batch
```

This runs the Strategist → Surgeon → Auditor loop once per listing found
by the Scout, saving:

- `outputs/{company}_{job_id}/resume.docx` — one folder per listing
- `outputs/batch_summary.csv` — columns: `job_title, company, url, ats_score, keyword_coverage, approved`

Note: batch mode makes several Anthropic API calls per listing (roughly
3-9 depending on retries), so fetching many listings can mean many dozens
of API calls. Use `--max-listings` to control cost.

## Output files

- `data/scout_report.json` — the market intelligence report from the Scout
- `data/strategy_report.json` — the last StrategyReport produced (single mode)
- `outputs/` — final tailored `.docx` resume(s), and `batch_summary.csv` in batch mode

## Project structure

```
job_hunt_agents/
├── main.py              # Orchestrator — runs the full pipeline
├── config.py             # API keys, model settings, target role config
├── schemas.py             # Pydantic models for all four agent reports
├── agents/
│   ├── scout.py          # Agent 1: finds and analyses job listings
│   ├── strategist.py     # Agent 2: scores resume, finds gaps, recommends reorder
│   ├── surgeon.py        # Agent 3: rewrites bullets in XYZ format, injects keywords
│   └── auditor.py        # Agent 4: ATS compliance check and final score
├── utils/
│   ├── resume_parser.py   # Reads PDF or DOCX resume into structured text
│   ├── job_scraper.py     # Searches and fetches job listings via Serper
│   ├── doc_writer.py      # Writes final resume to .docx using python-docx
│   └── anthropic_client.py # Shared retry/backoff + tool-use JSON helper
├── data/
│   └── resume.pdf         # Drop your current resume here
└── outputs/                # One subfolder per job, containing tailored resume
```

## Notes on reliability

- All Anthropic API calls use forced tool-use so every agent's output is
  schema-validated JSON (via Pydantic) rather than free-text that might not
  parse.
- Transient API errors (rate limits, timeouts, 5xx) are retried with
  exponential backoff (configurable in `config.py` via `MAX_API_RETRIES`,
  `INITIAL_BACKOFF_SECONDS`, `BACKOFF_MULTIPLIER`).
- If the Auditor rejects a resume, the Surgeon is re-run with the specific
  `issues_found` as extra instructions, up to `MAX_SURGEON_RETRIES` times
  (default 2). The best attempt is always written out, even if never
  approved — check the console summary's `Approved` field.
