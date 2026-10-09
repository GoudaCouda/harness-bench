from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def expand_schedules(schedules, window, overrides):
    """Broken: fixed UTC arithmetic ignores local recurrence and DST."""
    start_window = datetime.fromisoformat(window["start"].replace("Z", "+00:00"))
    end_window = datetime.fromisoformat(window["end"].replace("Z", "+00:00"))
    rows = []
    for schedule in schedules:
        local = datetime.fromisoformat(schedule["start_local"]).replace(tzinfo=ZoneInfo(schedule["timezone_history"][0]["timezone"]))
        for index in range(schedule["count"]):
            instant = local.astimezone(timezone.utc) + timedelta(days=index * schedule["interval"])
            if start_window <= instant < end_window:
                rows.append({"occurrence_id":f'{schedule["schedule_id"]}#{index+1:04d}',"nominal_local":schedule["start_local"],"scheduled_local":schedule["start_local"],"timezone":schedule["timezone_history"][0]["timezone"],"utc_start":instant.strftime("%Y-%m-%dT%H:%M:%SZ"),"utc_end":(instant+timedelta(minutes=schedule["duration_minutes"])).strftime("%Y-%m-%dT%H:%M:%SZ"),"resolution":"normal","override_applied":False})
    return {"occurrences": rows, "skipped": []}
