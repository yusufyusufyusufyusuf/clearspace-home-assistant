# ClearSpace Home Assistant Integration

Custom integration for ClearSpace in Home Assistant.

## What this supports

- Multiple ClearSpace API keys as separate Home Assistant entries
- A configurable entity prefix for each account
- A configurable refresh interval
- A default account for service calls
- Service targeting by `entry_id` or `entity_prefix`

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "ClearSpace" in HACS
3. Click Download
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/clearspace` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & services → Add integration**
2. Search for **ClearSpace**
3. Enter the account name, API token, and API URL
4. Optionally change the entity prefix and refresh interval
5. If you have more than one ClearSpace account, mark one as the default for services

## Entity names

Each account creates its own sensors using the entity prefix you choose.

Example with prefix `clearspace`:
- `sensor.clearspace_tasks`
- `sensor.clearspace_open`
- `sensor.clearspace_due_today`
- `sensor.clearspace_overdue`

If you add a second account, give it a different prefix like `work` or `personal`.

## Services

The integration exposes:

- `clearspace.create_task`
- `clearspace.complete_task`
- `clearspace.delete_task`
- `clearspace.refresh`

You can target a specific account with either:

- `entry_id`
- `entity_prefix`

If you omit both, Home Assistant uses the entry marked as default.

## Example service call

```yaml
action: clearspace.create_task
data:
  entity_prefix: work
  name: "Follow up with client"
  priority: high
  due: "2026-09-08"
```

## Dashboard cards

The ClearSpace cards read from the task entity attributes. If you change the entity prefix, update the dashboard entity accordingly.

## Docs

Open the setup and gallery page:

- `docs/index.html`
