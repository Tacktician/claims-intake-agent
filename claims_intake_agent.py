"""PostFinancial Claims Intake Agent.

Triages a first notice of loss (FNOL) for an auto or homeowners claim: it reads a
claim file, asks Claude for a structured triage, and prints the result for the
adjuster who picks the claim up.

This is the "before" version used in Introduction to Fabric, Lesson 8. It calls
Anthropic directly with a provider key read from ANTHROPIC_API_KEY. The lesson
changes the client block below so the agent calls Fabric instead. The finished
version is in solution/claims_intake_agent.py.

Usage:
    python claims_intake_agent.py sample_claims/CLM-1001.json
    python claims_intake_agent.py --all
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Literal

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-sonnet-5-5"
SAMPLE_DIR = Path(__file__).resolve().parent / "sample_claims"

SYSTEM_PROMPT = """You are the Claims Intake Agent for PostFinancial Solutions, a property and \
casualty insurer that writes auto and homeowners policies.

You triage first notice of loss (FNOL) submissions for the claims adjuster who will pick \
the claim up. You never talk to the policyholder, and you never approve, deny, or pay a \
claim. Your output is a recommendation for a human adjuster.

For each claim:
- Classify the line of business and the loss category.
- Rate severity as low, medium, or high, based on the described damage, injuries, and \
whether the property is usable.
- Recommend a referral to the Special Investigations Unit (SIU) only when the claim shows \
concrete fraud indicators, such as a loss reported shortly after the policy started or \
after coverage was increased, inconsistent accounts, or a prior claim pattern. List each \
indicator you relied on. Do not refer a claim on a hunch.
- List any information the adjuster needs that the claim does not include.
- Recommend one concrete next step for the adjuster.

Use only the facts in the claim file. If something is missing or unclear, say so in \
missing_information instead of guessing."""


class ClaimTriage(BaseModel):
    """Structured triage the agent hands to the adjuster."""

    claim_id: str
    line_of_business: Literal["auto", "home"]
    loss_category: str = Field(description="Short label, for example 'rear-end collision' or 'water damage'.")
    severity: Literal["low", "medium", "high"]
    severity_reason: str
    siu_referral: bool
    siu_indicators: List[str] = Field(description="Concrete fraud indicators. Empty when siu_referral is false.")
    missing_information: List[str]
    recommended_next_step: str
    adjuster_summary: str = Field(description="Two or three sentences for the adjuster.")


# --- Anthropic client ---------------------------------------------------------
# Lesson 8 changes this block so the agent calls Fabric instead of Anthropic.
client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
)
# ------------------------------------------------------------------------------


def triage_claim(claim: dict) -> ClaimTriage:
    """Send one claim to Claude and return the validated triage."""
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": "Triage this claim:\n\n" + json.dumps(claim, indent=2),
            }
        ],
        output_format=ClaimTriage,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined to triage claim {claim.get('claim_id')}.")
    print(
        f"  [request {response._request_id}] "
        f"{response.usage.input_tokens} input / {response.usage.output_tokens} output tokens"
    )
    return response.parsed_output


def print_triage(triage: ClaimTriage) -> None:
    flag = "YES" if triage.siu_referral else "no"
    print(f"\nClaim {triage.claim_id}  ({triage.line_of_business}, {triage.loss_category})")
    print(f"  Severity:      {triage.severity}. {triage.severity_reason}")
    print(f"  SIU referral:  {flag}")
    for indicator in triage.siu_indicators:
        print(f"    - {indicator}")
    if triage.missing_information:
        print("  Missing info:")
        for item in triage.missing_information:
            print(f"    - {item}")
    print(f"  Next step:     {triage.recommended_next_step}")
    print(f"  Summary:       {triage.adjuster_summary}\n")


def load_claims(paths: List[Path]) -> List[dict]:
    claims = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            claims.append(json.load(handle))
    return claims


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage PostFinancial FNOL claims with Claude.")
    parser.add_argument("claim_files", nargs="*", type=Path, help="Claim JSON files to triage.")
    parser.add_argument("--all", action="store_true", help="Triage every claim in sample_claims/.")
    args = parser.parse_args()

    paths = sorted(SAMPLE_DIR.glob("*.json")) if args.all else args.claim_files
    if not paths:
        parser.error("pass one or more claim files, or --all")

    try:
        for claim in load_claims(paths):
            print(f"Triaging {claim.get('claim_id', '?')}...")
            print_triage(triage_claim(claim))
    except anthropic.AuthenticationError:
        print("Authentication failed: check the credential the client sends.", file=sys.stderr)
        return 1
    except anthropic.PermissionDeniedError:
        print("Request was rejected (403): check the credential and its permissions.", file=sys.stderr)
        return 1
    except anthropic.NotFoundError:
        print("Not found (404): check the base URL and the model name.", file=sys.stderr)
        return 1
    except anthropic.RateLimitError:
        print("Rate limited (429): wait a moment and try again.", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as error:
        print(f"API error {error.status_code}: {error.message}", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("Could not connect: check your network and the base URL.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
