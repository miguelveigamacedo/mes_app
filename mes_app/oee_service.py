# app/oee_service.py
from datetime import datetime

def _to_naive_dt(value):
    """Convert DB value (str or datetime) to naive datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        # strip tzinfo if present
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        # try ISO first, then MySQL-style
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    # unexpected type
    raise ValueError(f"Unsupported datetime type: {type(value)}")


def build_enriched_events(rows, start_ts: datetime, end_ts: datetime):
    # make sure boundaries are naive datetimes
    if start_ts.tzinfo is not None:
        start_ts = start_ts.replace(tzinfo=None)
    if end_ts.tzinfo is not None:
        end_ts = end_ts.replace(tzinfo=None)

    enriched = []
    pointer = start_ts

    for r in rows:
        cs = _to_naive_dt(r["clipped_start_ts"])
        ce = _to_naive_dt(r["clipped_end_ts"])
        raw_dur = r["adj_duration_sec"]

        if cs is None or ce is None or raw_dur is None:
            continue

        dur_sec = int(raw_dur)
        if dur_sec <= 0:
            continue

        # gap before this event → synthetic MISSING event
        if cs > pointer:
            gap_sec = int((cs - pointer).total_seconds())
            if gap_sec > 0:
                enriched.append(
                    {
                        "start_ts": pointer,
                        "end_ts": cs,
                        "duration_sec": gap_sec,
                        "state_bucket": "UPDT",
                        "reason_code": "MISSING",
                        "reason_category": "UPDT",
                        "is_missing": True,
                        "workorder": None,
                        "comment": None,
                        "units_total": 0.0,
                        "waste_total": 0.0,
                        "target_speed_ups": None,
                    }
                )

        # compute scaled quantities for the clipped interval
        base_dur = r.get("base_duration_sec") or 0
        raw_units = r.get("units_total") or 0
        raw_waste = r.get("waste_total") or 0
        target_speed = r.get("target_speed_ups")

        if base_dur and base_dur > 0 and dur_sec > 0:
            scale = dur_sec / base_dur
        else:
            scale = 0.0

        units = raw_units * scale
        waste = raw_waste * scale

        # real event
        enriched.append(
            {
                "start_ts": cs,
                "end_ts": ce,
                "duration_sec": dur_sec,
                "state_bucket": r["state_bucket"],
                "reason_code": r["reason_code"],
                "reason_category": r["reason_category"],
                "is_missing": False,
                "workorder": r["workorder"],
                "comment": r.get("comment"),
                "units_total": units,
                "waste_total": waste,
                "target_speed_ups": target_speed,
            }
        )


        pointer = ce

    # tail gap after last event
    if pointer < end_ts:
        gap_sec = int((end_ts - pointer).total_seconds())
        if gap_sec > 0:
            enriched.append(
                {
                    "start_ts": pointer,
                    "end_ts": end_ts,
                    "duration_sec": gap_sec,
                    "state_bucket": "UPDT",
                    "reason_code": "MISSING",
                    "reason_category": "UPDT",
                    "is_missing": True,
                    "workorder": None,
                    "comment": None,
                    "units_total": 0.0,
                    "waste_total": 0.0,
                    "target_speed_ups": None,
                }
            )

    return enriched


def compute_totals(enriched_events, start_ts: datetime, end_ts: datetime):
    total_interval_sec = int((end_ts - start_ts).total_seconds())
    uptime_sec = 0
    missing_sec = 0
    updt_sec = 0
    bucket_secs = {"RUNNING": 0, "PDT": 0, "UPDT": 0, "OFF": 0, "OFF_NO_SHIFT": 0, "OTHER": 0}

    for e in enriched_events:
        sec = e["duration_sec"]
        bucket = e["state_bucket"]
        is_missing = e["is_missing"]

        if bucket in bucket_secs:
            bucket_secs[bucket] += sec
        else:
            bucket_secs["OTHER"] += sec

        if bucket == "RUNNING" and not is_missing:
            uptime_sec += sec
        if bucket == "UPDT" and not is_missing:
            updt_sec += sec
        if is_missing:
            missing_sec += sec

    updt_plus_missing_sec = updt_sec + missing_sec

    totals = [
        {"metric": "TOTAL_INTERVAL", "minutes": total_interval_sec / 60.0},
        {"metric": "UPTIME", "minutes": uptime_sec / 60.0},
        {"metric": "MISSING_TIME", "minutes": missing_sec / 60.0},
        {"metric": "UPDT_PLUS_MISSING", "minutes": updt_plus_missing_sec / 60.0},
    ]
    for name, sec in bucket_secs.items():
        totals.append({"metric": name, "minutes": sec / 60.0})

    return totals


def compute_by_reason(enriched_events):
    by_reason_map: dict[tuple[str, str], int] = {}
    for e in enriched_events:
        if e["is_missing"]:
            continue
        key = (e["reason_code"], e["reason_category"])
        by_reason_map[key] = by_reason_map.get(key, 0) + e["duration_sec"]

    by_reason = [
        {"reason_code": rc, "reason_category": cat, "minutes": sec / 60.0}
        for (rc, cat), sec in by_reason_map.items()
    ]
    by_reason.sort(key=lambda x: x["minutes"], reverse=True)
    return by_reason

def compute_stop_stats(enriched_events, start_ts: datetime, end_ts: datetime):
    """
    Per UPDT stop reason:
    - stop_count
    - total_downtime_min
    - mttr_min (mean time to repair)
    - mtbf_min (mean time between failures) based on full interval
    """
    if start_ts.tzinfo is not None:
        start_ts = start_ts.replace(tzinfo=None)
    if end_ts.tzinfo is not None:
        end_ts = end_ts.replace(tzinfo=None)

    total_interval_sec = int((end_ts - start_ts).total_seconds())
    stats_map: dict[tuple[str, str], dict] = {}

    for e in enriched_events:
        if e["is_missing"]:
            continue
        if e["state_bucket"] != "UPDT":
            continue

        key = (e["reason_code"], e["reason_category"])
        if key not in stats_map:
            stats_map[key] = {"stop_count": 0, "downtime_sec": 0}

        stats_map[key]["stop_count"] += 1
        stats_map[key]["downtime_sec"] += e["duration_sec"]

    stop_stats = []
    for (rc, cat), agg in stats_map.items():
        count = agg["stop_count"]
        dt_sec = agg["downtime_sec"]
        if count <= 0:
            continue

        mttr_sec = dt_sec / count
        mtbf_sec = total_interval_sec / count

        stop_stats.append(
            {
                "reason_code": rc,
                "reason_category": cat,
                "stop_count": count,
                "total_downtime_min": dt_sec / 60.0,
                "mttr_min": mttr_sec / 60.0,
                "mtbf_min": mtbf_sec / 60.0,
            }
        )

    stop_stats.sort(key=lambda x: x["total_downtime_min"], reverse=True)
    return stop_stats


def compute_system_stop_stats(enriched_events, start_ts: datetime, end_ts: datetime):
    """
    System-level PDT and UPDT stats:
    - stop_count
    - total_downtime_min
    - avg_stop_min
    - mtbf_min (only for UPDT, None for PDT)
    """
    if start_ts.tzinfo is not None:
        start_ts = start_ts.replace(tzinfo=None)
    if end_ts.tzinfo is not None:
        end_ts = end_ts.replace(tzinfo=None)

    total_interval_sec = int((end_ts - start_ts).total_seconds())

    pdt_count = pdt_sec = 0
    updt_count = updt_sec = 0

    for e in enriched_events:
        if e["is_missing"]:
            continue
        if e["state_bucket"] == "PDT":
            pdt_count += 1
            pdt_sec += e["duration_sec"]
        elif e["state_bucket"] == "UPDT":
            updt_count += 1
            updt_sec += e["duration_sec"]

    system_stats = []

    # PDT
    if pdt_count > 0:
        system_stats.append(
            {
                "bucket": "PDT",
                "stop_count": pdt_count,
                "total_downtime_min": pdt_sec / 60.0,
                "avg_stop_min": (pdt_sec / pdt_count) / 60.0,
                "mtbf_min": None,  # MTBF not meaningful for planned stops
            }
        )
    else:
        system_stats.append(
            {
                "bucket": "PDT",
                "stop_count": 0,
                "total_downtime_min": 0.0,
                "avg_stop_min": None,
                "mtbf_min": None,
            }
        )

    # UPDT
    if updt_count > 0:
        mttr_sec = updt_sec / updt_count
        mtbf_sec = total_interval_sec / updt_count
        system_stats.append(
            {
                "bucket": "UPDT",
                "stop_count": updt_count,
                "total_downtime_min": updt_sec / 60.0,
                "avg_stop_min": mttr_sec / 60.0,
                "mtbf_min": mtbf_sec / 60.0,
            }
        )
    else:
        system_stats.append(
            {
                "bucket": "UPDT",
                "stop_count": 0,
                "total_downtime_min": 0.0,
                "avg_stop_min": None,
                "mtbf_min": None,
            }
        )

    return system_stats


def compute_oee(enriched_events):
    """
    OEE with three components:
    - Availability: runtime / (runtime + PDT + UPDT)
    - Performance: actual_good / theoretical_good_at_target_speed
    - Quality: actual_good / (actual_good + scrap)
    Also returns absolute speed and quality losses for use in loss trees.
    """
    running_sec = 0
    pdt_sec = 0
    updt_sec = 0

    good_units = 0.0
    scrap_units = 0.0
    theoretical_good_units = 0.0

    for e in enriched_events:
        sec = e["duration_sec"]
        bucket = e["state_bucket"]

        # time buckets
        if bucket == "RUNNING":
            running_sec += sec
        elif bucket == "PDT":
            pdt_sec += sec
        elif bucket == "UPDT":
            updt_sec += sec

        # production only during real running time (no missing)
        if bucket == "RUNNING" and not e.get("is_missing", False):
            u = float(e.get("units_total", 0.0) or 0.0)
            w = float(e.get("waste_total", 0.0) or 0.0)
            good_units += u
            scrap_units += w

            tgt = e.get("target_speed_ups")
            if tgt is not None and tgt > 0 and sec > 0:
                theoretical_good_units += float(tgt) * float(sec)

    planned_sec = running_sec + pdt_sec + updt_sec

    if planned_sec <= 0:
        return {
            "planned_time_min": 0.0,
            "runtime_min": 0.0,
            "pdt_min": 0.0,
            "updt_min": 0.0,
            "availability": None,
            "performance": None,
            "quality": None,
            "oee": None,
            "good_units": 0.0,
            "scrap_units": 0.0,
            "total_units": 0.0,
            "theoretical_good_units": 0.0,
            "speed_loss_units": None,
            "quality_loss_units": None,
            "availability_loss_pct": None,
            "performance_loss_pct": None,
            "quality_loss_pct": None,
        }

    availability = running_sec / planned_sec

    total_units = good_units + scrap_units
    quality = (good_units / total_units) if total_units > 0 else None

    performance = (
        good_units / theoretical_good_units
        if theoretical_good_units > 0
        else None
    )

    oee = None
    if availability is not None and performance is not None and quality is not None:
        oee = availability * performance * quality

    # losses in absolute units and as percentages
    speed_loss_units = (
        theoretical_good_units - good_units
        if theoretical_good_units > 0
        else None
    )
    quality_loss_units = scrap_units

    availability_loss_pct = 1.0 - availability if availability is not None else None
    performance_loss_pct = 1.0 - performance if performance is not None else None
    quality_loss_pct = 1.0 - quality if quality is not None else None

    return {
        "planned_time_min": planned_sec / 60.0,
        "runtime_min": running_sec / 60.0,
        "pdt_min": pdt_sec / 60.0,
        "updt_min": updt_sec / 60.0,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee,
        "good_units": good_units,
        "scrap_units": scrap_units,
        "total_units": total_units,
        "theoretical_good_units": theoretical_good_units,
        "speed_loss_units": speed_loss_units,
        "quality_loss_units": quality_loss_units,
        "availability_loss_pct": availability_loss_pct,
        "performance_loss_pct": performance_loss_pct,
        "quality_loss_pct": quality_loss_pct,
    }

def serialize_events(enriched_events):
    serialized = []

    for e in enriched_events:
        units = float(e.get("units_total", 0.0) or 0.0)
        waste = float(e.get("waste_total", 0.0) or 0.0)
        target_speed = e.get("target_speed_ups")

        quality_loss_units = waste

        speed_loss_units = 0.0 if e["state_bucket"] != "RUNNING" else None

        if (
            e["state_bucket"] == "RUNNING"
            and target_speed is not None
            and target_speed > 0
            and e["duration_sec"] > 0
        ):
            theoretical_good_units = float(target_speed) * float(e["duration_sec"])
            speed_loss_units = theoretical_good_units - units
            if speed_loss_units < 0:
                speed_loss_units = 0.0

        serialized.append(
            {
                "start_ts": e["start_ts"].isoformat(),
                "end_ts": e["end_ts"].isoformat(),
                "minutes": e["duration_sec"] / 60.0,
                "state_bucket": e["state_bucket"],
                "reason_code": e["reason_code"],
                "reason_category": e["reason_category"],
                "is_missing": e["is_missing"],
                "workorder": e["workorder"],
                "comment": e.get("comment"),
                "units_total": units,
                "waste_total": waste,
                "target_speed_ups": target_speed,
                "quality_loss_units": quality_loss_units,
                "speed_loss_units": speed_loss_units,
            }
        )

    return serialized
