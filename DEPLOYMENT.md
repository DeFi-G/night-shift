# Night Shift - Cloud Deployment

## Overview

Night Shift was developed and qualified on Fly.io Sprites
using gateway-managed Ollama inference.

The repository includes the qualified V12 live application
and a separate credential-free mock evaluation launcher.

Mock evaluation is the recommended first step.

## Infrastructure Requirements

- A Fly.io account with Sprite access.
- A Linux Sprite with Python 3.
- An Ollama account and managed connector.
- Access to the gpt-oss:20b model.
- Optional Discord webhook for lifecycle notifications.

Official infrastructure documentation:

- https://fly.io/sprites/
- https://fly.io/sprites/ollama
- https://docs.fly.io/sprites/

## Deployment

Transfer the repository files into a new directory
on your own Sprite.

Do not reuse an existing production runtime or ledger.

Run all commands below from the repository directory.

## Authorization and Budget

The qualified live application is intentionally restricted
to a single authorized assignment.

Its inference ledger permits a maximum cumulative
reservation of USD 0.00768, corresponding to five
maximum-sized inference reservations.

The ledger uses internal pricing estimates.
Actual provider charges and infrastructure costs may differ.

Before initializing a fresh deployment, explicitly approve
the inference expenditure and verify current provider pricing.

Never reset an existing ledger to bypass its safeguards.

## Initialize a New Deployment

Only after authorization, initialize a new ledger:

    python3 -B -c 'from pathlib import Path; from inference_ledger import Ledger; Ledger.initialize(Path("ledger"))'

The initialization must fail if the ledger already exists.

## Configure Live Intelligence

Configure the following environment variables privately:

    export NIGHT_SHIFT_MODE=ollama
    export NIGHT_SHIFT_ALLOW_LIVE=YES
    export NIGHT_SHIFT_MODEL=gpt-oss:20b
    export NIGHT_SHIFT_CONNECTION=YOUR_CONNECTOR_ID

Replace the placeholder with your own authorized connector
identifier.

Authentication is managed by the Sprite gateway.
Do not embed an Ollama API key in the repository.

## Optional Discord Notifications

The qualified notification adapter reads its webhook from:

    /home/sprite/night-shift-private/discord-webhook

To enable notifications, provision this file privately
using your own webhook URL.

Restrict the directory to mode 700 and the file to mode 600.

Do not commit, print, or share the webhook credential.

Without a configured webhook, notification delivery is
unavailable. The standalone mock evaluator does not
invoke the notification adapter.

## Start the Live Application

From the repository directory:

    python3 -B app.py --data runtime --port 8080

The application binds to the loopback interface.

Use an authenticated Sprite proxy to access the dashboard.
Do not expose the dashboard directly to the public internet.

For persistent execution, configure a Sprite-managed
service using the same working directory and private
environment configuration.

The Sprite service and connector configuration are
deployment-specific.

## Dashboard Authentication

Username:

    owner

The application generates its password in:

    runtime/owner-password

Retrieve this password privately.

## Assignment Lifecycle

The application stores assignment state in SQLite.

The worker requests a bounded Sprite task hold during
cloud assignment execution and releases it afterward.

Lifecycle states include READY, QUEUED, CLOCKED_IN,
WORKING, VERIFYING, and COMPLETED.

Failed, cancelled, or interrupted assignments are
represented separately.

## Shutdown and Safeguards

The live demonstration authorization is consumed when
the first assignment is admitted.

The application disables further inference following
terminal execution, cancellation, or qualifying failure.

A consumed authorization must not be reused.

Stop the application or its managed service after
evaluation.

Preserve the ledger and runtime authorization marker.

## Reproducibility Notes

The original V12 live deployment completed a genuine
Ollama assignment with three inference requests and
two delivered Discord lifecycle notifications.

Detached execution was demonstrated separately in V9.3.

The standalone mock launcher has passed end-to-end
HTTP evaluation on Linux.

This deployment guide describes the qualified architecture.
A fresh third-party live deployment has not been
independently executed or qualified.

## Security

Never publish:

- Connector credentials or private configuration.
- Discord webhook URLs.
- Dashboard owner passwords.
- Runtime databases.
- Private uploaded project files.
- Live inference ledgers.

Night Shift is a bounded hackathon MVP, not an
unrestricted production automation platform.
