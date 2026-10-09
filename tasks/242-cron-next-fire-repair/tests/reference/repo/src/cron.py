"""Next-fire helper for the mill 30-day cron clock."""


def next_fire(expr, after):
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("expr")
    minute_f, hour_f, day_f, month_f, dow_f = parts

    def parse_field(field, lo, hi):
        if field == "*":
            return set(range(lo, hi + 1))
        values = set()
        for part in field.split(","):
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start = int(start_s)
                end = int(end_s)
                for value in range(start, end + 1):
                    if lo <= value <= hi:
                        values.add(value)
            else:
                value = int(part)
                if lo <= value <= hi:
                    values.add(value)
        if not values:
            raise ValueError("empty_field")
        return values

    minutes = parse_field(minute_f, 0, 59)
    hours = parse_field(hour_f, 0, 23)
    days = parse_field(day_f, 1, 30)
    months = parse_field(month_f, 1, 12)
    dows = parse_field(dow_f, 0, 6)
    month = int(after["month"])
    day = int(after["day"])
    hour = int(after["hour"])
    minute = int(after["minute"]) + 1
    for _step in range(30 * 12 * 24 * 60):
        if minute > 59:
            minute = 0
            hour += 1
        if hour > 23:
            hour = 0
            day += 1
        if day > 30:
            day = 1
            month += 1
        if month > 12:
            month = 1
        day_index = (month - 1) * 30 + (day - 1)
        dow = day_index % 7
        if month not in months or hour not in hours or minute not in minutes:
            minute += 1
            continue
        if day_f == "*" and dow_f == "*":
            date_ok = True
        elif day_f == "*":
            date_ok = dow in dows
        elif dow_f == "*":
            date_ok = day in days
        else:
            date_ok = day in days or dow in dows
        if date_ok:
            return {"month": month, "day": day, "hour": hour, "minute": minute}
        minute += 1
    raise ValueError("no_fire")
