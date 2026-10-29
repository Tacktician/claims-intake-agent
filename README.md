# PostFinancial Claims Intake Agent

A small Python agent that triages first notice of loss (FNOL) claims for PostFinancial Solutions, the fictional auto and homeowners insurer in the Postman Academy **Fabric** learning path. It reads a claim file, asks Claude for a structured triage (loss category, severity, SIU referral, missing information, next step), and prints the result for the adjuster.

It is the hands-on asset for **Introduction to Fabric, Lesson 8: Connect a Client**. The agent starts out calling Anthropic directly with a provider key in its config, which is exactly what Jordan's audit team flagged. In the lesson you change two things so it calls Fabric instead.

## What's here

| Path | What it is |
| --- | --- |
| `claims_intake_agent.py` | The **before** version. Calls Anthropic directly using `ANTHROPIC_API_KEY`. |
| `solution/claims_intake_agent.py` | The **after** version. Calls Fabric using `FABRIC_GATEWAY_URL` and `FABRIC_GATEWAY_KEY`. |
| `sample_claims/` | Three synthetic claims: a rear-end collision, a burst supply line, and a theft with fraud indicators. |
| `.env.example` | The environment variables each version reads. |

The two files are identical except for the client block (and their doc comments):

```python
# Before
client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
)

# After
client = anthropic.Anthropic(
    base_url=os.environ["FABRIC_GATEWAY_URL"],  # includes the /anthropic route
    api_key="not-used",  # Fabric injects the real Anthropic key upstream
    default_headers={"fg-api-key": os.environ["FABRIC_GATEWAY_KEY"]},
)
```

1. **Base URL:** your full gateway URL, including the `/anthropic` route prefix (no trailing slash). The SDK appends `/v1/messages` itself.
2. **Credential:** the gateway key, sent in the `fg-api-key` header. The SDK still requires an `api_key` value, so it gets a placeholder.

## Requirements

- Python 3.10 or later (the `anthropic` 1.x SDK requires it)
- An Anthropic API key, for the before version
- A Fabric tenant with an `anthropic` connection, route, and gateway key, for the after version (Introduction to Fabric, Lessons 4 to 6)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the before version

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python claims_intake_agent.py sample_claims/CLM-1001.json
python claims_intake_agent.py --all
```

## Point it at Fabric

Make the two-line change in `claims_intake_agent.py` (or run the solution file), then remove the provider key from your shell so it can't be used by accident:

```bash
unset ANTHROPIC_API_KEY
export FABRIC_GATEWAY_URL="https://<gateway-subdomain>.dp.fabricgateway.ai/anthropic"
export FABRIC_GATEWAY_KEY="<gateway-key>"
python solution/claims_intake_agent.py --all
```

The output is the same. The difference is where the call went: open **Observability → Traces** in the Fabric console, filter **Protocol = LLM** and **Route = anthropic**, and each triage shows up as its own trace. Each run also prints the request ID and token counts, which helps you match a run to its trace.

## Notes for course authors

- **Model:** `claude-sonnet-5-5`, matching the course's code samples. Update `MODEL` if the course changes it at recording time.
- **Structured output:** the agent uses `client.messages.parse()` with a Pydantic model, so the triage always comes back as validated fields. Claude Sonnet 5.5 doesn't accept a forced `tool_choice`, so structured outputs are the supported way to guarantee the shape.
- **Synthetic PII, on purpose:** each claim carries a policyholder SSN and driver's license number. They're fake (SSNs beginning with `000` are never issued), and the agent sends them to the model unmasked. That's the "policy drift" problem from Lesson 1, and it gives Course 3 (Governing Traffic with Plugins) something real to redact with a fail-closed policy in Fabric.
- **SIU referral:** `CLM-1003` is built to trigger one (a policy two weeks old, coverage raised a week before the loss, no police report, three prior claims). The other two should not.
- **Not production code:** no retries beyond the SDK defaults, no persistence, no UI. It's sized to fit on screen in a video.
