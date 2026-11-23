# GTFS-Realtime collector

> **Not in use.** Shelved on 2026-11-23: scheduled times are taken as good enough for now, so
> nothing is being archived and layer 6b is not planned. The code is kept, tested, in case that changes.

Small standalone archiver (brief 6b / 14.6). Polls public vehicle-position feeds of Polish cities every 20-30 s and writes
daily Parquet partitions. It is **not** part of the build or CI and keeps its data **outside the repo**
(the process refuses an archive dir inside the repo, except `collector/archive/`, which is gitignored and meant for tests).
Feed survey and licences: `FEEDS.md`; feed registry: `feeds.yaml`.

## Install and run

```bash
./.venv/Scripts/python.exe -m pip install -r collector/requirements.txt   # Windows venv of the repo
./.venv/Scripts/python.exe -m collector.run --archive-dir D:/gtfsrt-archive              # run forever
./.venv/Scripts/python.exe -m collector.run --archive-dir D:/gtfsrt-archive --feeds krakow_t,szczecin
./.venv/Scripts/python.exe -m collector.run --archive-dir D:/gtfsrt-archive --once        # one poll per feed
./.venv/Scripts/python.exe -m collector.run --archive-dir D:/gtfsrt-archive --trip-updates # also capture TripUpdates (off by default)
./.venv/Scripts/python.exe -m collector.run compact --archive-dir D:/gtfsrt-archive        # merge parts of finished days
```

Other options: `--duration-s N`, `--flush-s 300`. `--feeds` overrides `enabled:` in `feeds.yaml`. Stop with Ctrl+C / SIGTERM
(buffers are flushed). `powershell -ExecutionPolicy Bypass -File collector\start.ps1 -ArchiveDir D:\gtfsrt-archive` runs it
with a restart-on-crash loop (config errors, exit code 2, are not retried).

Archive layout (partition date = Europe/Warsaw day of `fetched_at`):

```
<archive>/<feed_id>/date=YYYY-MM-DD/part-HHMMSS.parquet     (compact -> part-compacted.parquet)
<archive>/<feed_id>-tripupdates/date=.../                    (only with --trip-updates)
<archive>/_log/gaps.jsonl  status.json  collector.log
```

Columns (vehicles): `fetched_at, feed_ts, vehicle_ts, vehicle_id, trip_id, route_id, start_date, start_time, direction_id,
lat, lon, bearing, speed (m/s), current_stop_sequence, stop_id, current_status, label` (nulls where the feed has no value).
Rows identical to the previous observation of the same vehicle (same `vehicle_ts` and position) are dropped. Warsaw `route_id`
is derived from `trip_id` (feed leaves it empty); Gdansk JSON speed is converted from km/h. Read it with
`pyarrow.dataset.dataset(dir, format="parquet", partitioning="hive")`.

## Behaviour

One thread per feed (a slow or dead feed does not delay others); timeouts 5 s connect / 20 s read; jitter +-10%;
`If-None-Match` / `If-Modified-Since`; exponential backoff after errors up to 300 s, `Retry-After` honoured on 429.
A feed whose timestamp does not advance for 10 min is treated as an outage ("stale").

**Gaps:** `_log/gaps.jsonl` gets one JSON line per outage (>= 2 consecutive failed polls) per feed: `feed, start` (last good poll),
`end` (first good poll after), `duration_s, reason, consecutive_failures, first_failure`. Records with `feed: "_collector"`
mean the whole process was not running (crash, reboot, stopped). Check:

```bash
./.venv/Scripts/python.exe -c "import pandas as pd; g=pd.read_json('D:/gtfsrt-archive/_log/gaps.jsonl', lines=True); print(g.groupby('feed').duration_s.agg(['count','sum','max']))"
type D:\gtfsrt-archive\_log\status.json      # heartbeat, refreshed every minute: last success, rows today, last error per feed
```

## Run 24/7 (owner's decision; commands are NOT executed by this repo)

Windows Task Scheduler, at logon (machine must stay on and awake):

```powershell
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\path\to\compactness\collector\start.ps1 -ArchiveDir D:\gtfsrt-archive"
$t = New-ScheduledTaskTrigger -AtLogOn
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "GtfsRtCollector" -Action $a -Trigger $t -Settings $s
# remove: Unregister-ScheduledTask -TaskName GtfsRtCollector -Confirm:$false
```

Small Linux VPS with systemd (`/etc/systemd/system/gtfsrt-collector.service`; clone repo to `/opt/compactness`, `python3 -m venv .venv && .venv/bin/pip install -r collector/requirements.txt`):

```ini
[Unit]
Description=GTFS-RT collector
After=network-online.target
Wants=network-online.target
[Service]
User=gtfsrt
WorkingDirectory=/opt/compactness
ExecStart=/opt/compactness/.venv/bin/python -m collector.run --archive-dir /var/lib/gtfsrt-archive
Restart=always
RestartSec=15
RestartPreventExitStatus=2
[Install]
WantedBy=multi-user.target
```
```bash
sudo useradd -r -m gtfsrt && sudo mkdir -p /var/lib/gtfsrt-archive && sudo chown gtfsrt: /var/lib/gtfsrt-archive
sudo systemctl daemon-reload && sudo systemctl enable --now gtfsrt-collector
journalctl -u gtfsrt-collector -f
```

A daily `compact` (cron/systemd timer) is optional; it only touches days before today.

## Disk usage

Measured on a 4-minute evening run (zstd, compacted), extrapolated to 16 effective hours/day; treat as +-50 %:

| feed | MB/day | notes |
|---|---|---|
| warsaw | ~57 | ~1900 vehicles, 3.4 M rows/day |
| poznan | ~13 | |
| gdansk | ~9 | |
| szczecin | ~8 | |
| krakow_t / krakow_a / krakow_m | ~7 / ~5 / ~5 | |
| **all vehicle feeds** | **~100 MB/day, ~2.9 GB per 28 days** | |
| TripUpdates (opt-in, all feeds) | ~+80 MB/day | Krakow dominates; not needed for speeds |

Bandwidth is about 0.5 GB/day (mostly Warsaw, 178 KB per poll).

## Licences (details in FEEDS.md)

Warsaw: Warsaw Open Data terms, attribution required ("Miasto Stoleczne Warszawa", download date, api.um.warszawa.pl). Krakow: CC BY 4.0 (ZTP).
Szczecin: CC0 (100 req/min/IP limit). Gdansk: CC BY. Poznan and GZM: terms not verified.
Wroclaw, Lodz, Gdynia: no usable real-time feed found/verified.

## Tests

`./.venv/Scripts/python.exe -m pytest collector/tests -q`
