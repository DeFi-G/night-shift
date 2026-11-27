# Night Shift

![Night Shift](web/logo.png)

**Clock out. We'll clock in.**

An asynchronous AI workforce application built by DeFi Network
for Hacksgiving 2026.

## The Problem

Independent creators and small teams spend valuable working
hours reviewing files, checking production schedules, identifying
outstanding tasks, and preparing reports.

Most conversational AI workflows still require an operator
to remain involved throughout the process.

Night Shift explores a different approach: assign the work,
disconnect, and return to documented results.

## How It Works

1. Describe an assignment.
2. Upload the relevant project files.
3. Select Assign & Clock Out.
4. Night Shift processes the assignment in the background.
5. Receive lifecycle notifications when configured.
6. Return to an evidence-backed report.

## Architecture

- Fly.io Sprites: persistent cloud execution environment.
- Ollama: live model inference through a managed connector.
- GPT-OSS 20B: qualified live demonstration model.
- Python: application, worker, and inspection tools.
- SQLite: persistent assignments and lifecycle records.
- HTML, CSS, JavaScript: responsive dashboard.
- Discord: optional outbound lifecycle notifications.

## Features

- Asynchronous assignment execution.
- Persistent assignment history.
- Bounded file inspection and evidence collection.
- Model-directed tool selection in live mode.
- Input integrity verification.
- Markdown and JSON report exports.
- Discord lifecycle notifications.
- Inference request and budget controls.
- Explicit single-use live demonstration authorization.

## Quick Start: Mock Evaluation

The standalone mock evaluator requires Python 3 on Linux.
It does not require an Ollama account, Discord webhook,
Sprite connector, or third-party Python packages.

From the repository directory:

    python3 -B run_mock.py --data runtime --port 8080

Open:

    http://127.0.0.1:8080

Username:

    owner

The application generates a password in:

    runtime/owner-password

Read that file locally to sign in. Do not publish its contents.

Upload both files from the demo directory:

- checklist.txt
- release.md

Example assignment:

    Identify outstanding TODO items and generate a report.

The expected result contains two outstanding TODO items
with supporting file and line references.

Mock mode uses deterministic simulated provider responses.
It does not perform genuine model reasoning, cloud task holds,
or Discord notification delivery.

Stop the application with Ctrl+C.

## Live Demonstration

The qualified live application uses Fly.io Sprites and
gateway-managed Ollama authentication.

Live operation requires separately configured infrastructure,
an initialized inference ledger, and explicit authorization.

The standalone mock launcher cannot activate live inference.

The qualified live demonstration was intentionally restricted
to one assignment and a maximum of five inference requests.

The original demonstration environment remains disabled
following successful qualification.

Live deployment configuration is documented separately.

## Qualification Results

### V12 Live Demonstration

- Model: GPT-OSS 20B
- Assignment status: COMPLETED
- Elapsed execution: 5.341 seconds
- Inference requests: 3
- Owner-reviewed accuracy: 5/5
- Synthetic safeguard checks: 29/29
- Discord clock-in notification: delivered
- Discord completion notification: delivered

The demonstration reviewed a production schedule and correctly
identified a total workload of 93 minutes, available production
time of 80 minutes, and a shortfall of 13 minutes.

Estimated inference cost: USD 0.00039285.

This is an internal inference estimate, not a provider invoice
or a measurement of total infrastructure costs.

### Detached Execution

Detached live execution was demonstrated separately in V9.3.
The V12 combined live demonstration completed while its
client remained connected.

### Standalone Mock Evaluation

The submission evaluator successfully completed:

- Credential-free startup.
- Authenticated dashboard access.
- HTTP assignment submission.
- Two-file inspection and expected TODO findings.
- Markdown and JSON report downloads.
- Temporary runtime cleanup.

## Evidence

The evidence directory contains the sealed V12 live
qualification record and demonstration reports.

These records describe the qualified demonstration environment,
not an unrestricted production deployment.

## Current Limitations

Night Shift is a hackathon MVP focused on bounded static
file inspection and evidence-backed reporting.

It does not provide unrestricted computer control,
arbitrary command execution, or general-purpose file editing.

Inspection is subject to documented sampling limits.
Discord notifications are best-effort.
The dashboard displays raw Markdown report formatting.

The standalone mock evaluator was qualified on Linux.
Native Windows execution has not been independently qualified.

## Built With

Fly.io Sprites, Ollama, GPT-OSS, Python, SQLite, and Discord.

## Developer

DeFi Network

Hacksgiving 2026

**Night Shift - Clock out. We'll clock in.**
