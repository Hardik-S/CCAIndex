from pathlib import Path

workflow = Path(".github/workflows/main.yml").read_text()

required_snippets = [
    "id: api-key-config",
    "configured=false",
    "::notice::Skipping climate data generation",
    "if: steps.api-key-config.outputs.configured == 'true'",
]

missing = [snippet for snippet in required_snippets if snippet not in workflow]

if missing:
    raise SystemExit(f"workflow is missing API key guard snippets: {missing}")

print("workflow skips climate data generation when API keys are not configured")
