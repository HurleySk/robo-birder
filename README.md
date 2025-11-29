# Robo-Birder

Push bird detection notifications from [BirdNet Go](https://github.com/tphakala/birdnet-go) to Discord via webhooks.

## Features

- **New Species Alerts**: Instant notifications when a never-before-seen species is detected (first ever, first of year, or first of season)
- **Scheduled Summaries**: Configurable daily, hourly, weekly, or custom interval reports
- **Bird Images**: Embeds include species photos from BirdNet Go's Wikimedia cache
- **Fully Configurable**: YAML config with per-summary webhooks, confidence thresholds, species filters, and more

## Requirements

- Python 3.10+
- BirdNet Go instance with SQLite output enabled
- Discord webhook URL

## Installation

```bash
# Clone the repository
git clone https://github.com/HurleySk/robo-birder.git
cd robo-birder

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit configuration
cp config.yaml.example config.yaml
nano config.yaml  # Add your Discord webhook URL
```

## Configuration

Edit `config.yaml`:

```yaml
discord:
  webhook_url: "https://discord.com/api/webhooks/YOUR/WEBHOOK"

# Instant alerts for new species
new_species:
  enabled: true
  min_confidence: 0.5
  notify_on:
    first_ever: true      # Never seen before
    first_of_year: true   # First of calendar year
    first_of_season: false

# Scheduled summaries (add as many as you want)
summaries:
  - name: "daily"
    enabled: true
    cron: "0 20 * * *"      # 8 PM daily
    lookback_minutes: 1440  # 24 hours
    include_top_species: 10

  - name: "hourly"
    enabled: false
    cron: "0 * * * *"
    lookback_minutes: 60
    include_top_species: 5

# BirdNet Go paths
birdnet:
  db_path: "/path/to/birdnet.db"
  base_url: "http://localhost:8080"
```

## Usage

### Manual Commands

```bash
# Send a test notification
sudo ./venv/bin/python notify_handler.py --test

# Trigger a summary manually
sudo ./venv/bin/python notify_handler.py --summary daily

# Process the latest detection
sudo ./venv/bin/python notify_handler.py
```

### Run as a Service

Create `/etc/systemd/system/robo-birder.service`:

```ini
[Unit]
Description=Robo-Birder Discord Notification Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/robo-birder
ExecStart=/path/to/robo-birder/venv/bin/python scheduler_daemon.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable robo-birder
sudo systemctl start robo-birder
```

### BirdNet Go Integration

To receive real-time detection notifications, configure BirdNet Go's script notification provider in its `config.yaml`:

```yaml
notification:
  push:
    enabled: true
    providers:
      - type: script
        enabled: true
        name: robo-birder
        filter:
          types:
            - detection
        command: /path/to/robo-birder/venv/bin/python
        args:
          - /path/to/robo-birder/notify_handler.py
```

Restart BirdNet Go after making changes.

## Discord Message Examples

### New Species Alert
A gold-colored embed appears when a species is detected for the first time:

> **NEW SPECIES DETECTED!**
>
> **Cedar Waxwing**
> *Bombycilla cedrorum*
>
> First ever sighting!
> Confidence: 72%
> Time: 2:30 PM

### Daily Summary
A summary of all detections over the configured period:

> **Daily Bird Report - Nov 29, 2025**
>
> **164** detections | **15** species
>
> Top Species:
> 1. House Sparrow (68)
> 2. American Robin (45)
> 3. Northern Cardinal (32)
> ...

## Service Management

```bash
# View logs
sudo journalctl -u robo-birder -f

# Reload config without restart
sudo systemctl reload robo-birder

# Restart service
sudo systemctl restart robo-birder

# Check status
sudo systemctl status robo-birder
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [BirdNet Go](https://github.com/tphakala/birdnet-go) - Real-time bird sound recognition
- [BirdNET](https://birdnet.cornell.edu/) - The neural network model by Cornell Lab of Ornithology
