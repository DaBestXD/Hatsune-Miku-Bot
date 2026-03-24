CREATE_EVENTS = """
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        event_time TEXT NOT NULL,
        details TEXT
        )
    """
CREATE_SNAPSHOTS = """
    CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('online', 'degraded', 'down')),
    discord_connection INTEGER NOT NULL CHECK (discord_connection IN (0, 1)),
    latency_ms REAL,
    uptime_seconds INTEGER NOT NULL
    )
    """
