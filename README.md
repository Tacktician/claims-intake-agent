# PostFinancial Claims Intake Agent

A small Python agent that triages first notice of loss (FNOL) claims for PostFinancial Solutions, the fictional auto and homeowners insurer in the Postman Academy **Fabric** learning path. It reads a claim file, asks Claude for a structured triage (loss category, severity, SIU referral, missing information, next step), and prints the result for the adjuster.

It is the hands-on asset for two courses: **Introduction to Fabric, Lesson 8: Connect a Client** and **Introduction to Passport, Lesson 3: Follow One Request with the Claims Agent**. The agent starts out calling Anthropic directly with a provider key, which is exactly what each course's scenario flags. Each course changes the client block so the key leaves the agent.

## What's here

| Path | What it is |
| --- | --- |
| `claims_intake_agent.py` | The **before** version, shared by both courses. Calls Anthropic directly using `ANTHROPIC_API_KEY`. |
| `solutions/fabric/claims_intake_agent.py` | The Fabric **after** version. Calls Fabric using `FABRIC_GATEWAY_URL` and `FABRIC_GATEWAY_KEY`. |
| `solutions/passport/claims_intake_agent.py` | The Passport **after** version. Sends a `{{vault:ANTHROPIC_API_KEY}}` reference and relies on the Passport Proxy to add the key. |
| `sample_claims/` | Three synthetic claims: a rear-end collision, a burst supply line, and a theft with fraud indicators. |
| `.env.example` | The environment variables each version reads. |

The three files are identical except for the client block (and their doc comments):

```python
# Before
client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
)

# After: Fabric
client = anthropic.Anthropic(
    base_url=os.environ["FABRIC_GATEWAY_URL"],  # includes the /anthropic route
    api_key="not-used",  # Fabric injects the real Anthropic key upstream
    default_headers={"fg-api-key": os.environ["FABRIC_GATEWAY_KEY"]},
)

# After: Passport
client = anthropic.Anthropic(
    api_key="{{vault:ANTHROPIC_API_KEY}}",  # a reference; the proxy adds the real key
)
```

**Fabric:** the base URL is your full gateway URL, including the `/anthropic` route prefix (no trailing slash). The SDK appends `/v1/messages` itself. The credential is the gateway key, sent in the `fg-api-key` header, and the SDK gets a placeholder `api_key`.

**Passport:** the agent still calls Anthropic. The change is that `api_key` is a secret reference, not a key. The call has to travel through a Passport connection (`passport setup`, or `passport lens run`) so the proxy can swap the reference for the real key.

## Requirements

- Python 3.10 or later (the `anthropic` 1.x SDK requires it)
- An Anthropic API key, for the before version
- **Fabric after version:** a Fabric tenant with an `anthropic` connection, route, and gateway key (Introduction to Fabric, Lessons 4 to 6)
- **Passport after version:** the Passport CLI connected to a proxy, with your Anthropic key stored in the proxy's secret store and the Anthropic API registered as a resource. For evaluation, the Passport plugin's `setup passport` skill runs a Local Docker proxy (needs Docker, `openssl`, `curl`, `jq`, and Node.js).

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

Run the Fabric solution, then remove the provider key from your shell so it can't be used by accident:

```bash
unset ANTHROPIC_API_KEY
export FABRIC_GATEWAY_URL="https://<gateway-subdomain>.dp.fabricgateway.ai/anthropic"
export FABRIC_GATEWAY_KEY="<gateway-key>"
python solutions/fabric/claims_intake_agent.py --all
```

The output is the same. The difference is where the call went: open **Observability → Traces** in the Fabric console, filter **Protocol = LLM** and **Route = anthropic**, and each triage shows up as its own trace. Each run also prints the request ID and token counts, which helps you match a run to its trace.

## Point it at Passport

With your machine connected to a Passport Proxy, remove the provider key and run the Passport solution:

```bash
unset ANTHROPIC_API_KEY
python solutions/passport/claims_intake_agent.py --all
```

To see the reference being swapped without a team proxy, wrap the run in the Passport inspector: `passport lens run python solutions/passport/claims_intake_agent.py sample_claims/CLM-1001.json`.

## Notes for course authors

- **Model:** `claude-sonnet-5-5`, matching the course's code samples. Update `MODEL` if the course changes it at recording time.
- **Structured output:** the agent uses `client.messages.parse()` with a Pydantic model, so the triage always comes back as validated fields. Claude Sonnet 5.5 doesn't accept a forced `tool_choice`, so structured outputs are the supported way to guarantee the shape.
- **Synthetic PII, on purpose:** each claim carries a policyholder SSN and driver's license number. They're fake (SSNs beginning with `000` are never issued), and the agent sends them to the model unmasked. That's the "policy drift" problem from Lesson 1, and it gives Course 3 (Governing Traffic with Plugins) something real to redact with a fail-closed policy in Fabric.
- **SIU referral:** `CLM-1003` is built to trigger one (a policy two weeks old, coverage raised a week before the loss, no police report, three prior claims). The other two should not.
- **Not production code:** no retries beyond the SDK defaults, no persistence, no UI. It's sized to fit on screen in a video.
