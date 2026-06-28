"""LangChain tools with mocked dealership business logic."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

from langchain_core.tools import tool

from agent.context import get_thread_context
from agent.customers import get_customer_by_phone
from metrics.store import (
    build_handover_package,
    log_booking,
    log_escalation,
    log_tool_event,
)

_current_thread_id: str = "default"

SERVICE_CENTERS = [
    {"city": "Dubai", "name": "Al-Futtaim Auto Center — Sheikh Zayed Road", "brands": "All makes"},
    {"city": "Dubai", "name": "Al-Futtaim Toyota — Deira", "brands": "Toyota, Lexus"},
    {"city": "Abu Dhabi", "name": "Al-Futtaim Auto Center — Mussafah", "brands": "All makes"},
    {"city": "Sharjah", "name": "Al-Futtaim Honda — Industrial Area", "brands": "Honda"},
]


def set_thread_id(thread_id: str) -> None:
    global _current_thread_id
    _current_thread_id = thread_id


RECALL_DATA: dict[tuple[str, str, int], list[dict]] = {
    ("toyota", "camry", 2020): [
        {"recall_id": "20V-123", "description": "Fuel pump may fail, increasing stall risk.", "status": "open"}
    ],
    ("honda", "civic", 2019): [],
    ("ford", "f-150", 2021): [
        {"recall_id": "21V-456", "description": "Windshield wiper motor may fail in heavy rain.", "status": "open"},
        {"recall_id": "21V-457", "description": "Rear camera display may intermittently blank.", "status": "open"},
    ],
    ("bmw", "x3", 2018): [
        {"recall_id": "18V-789", "description": "Passenger airbag inflator may rupture.", "status": "open"}
    ],
}

CONDITION_MULTIPLIERS = {"excellent": 1.0, "good": 0.85, "fair": 0.65, "poor": 0.45}


@tool
def get_customer_profile(phone: str) -> str:
    """Look up a returning customer's profile and vehicles on file.

    Args:
        phone: Customer mobile number (e.g. +971501234567).
    """
    profile = get_customer_by_phone(phone)
    if not profile:
        return f"No profile found for {phone}. I can still help as a guest."
    lines = [
        f"Customer: {profile['name']} ({profile['loyalty_tier']})",
        f"ID: {profile['customer_id']}",
        "Vehicles on file:",
    ]
    for v in profile["vehicles"]:
        lines.append(
            f"  - {v['year']} {v['make']} {v['model']} (plate {v['plate']}, "
            f"last service {v['last_service']}, open recalls: {v['open_recalls']})"
        )
    return "\n".join(lines)


@tool
def find_service_center(city: str, brand: str = "any") -> str:
    """Find Al-Futtaim service centres near a UAE city.

    Args:
        city: City name (e.g. Dubai, Abu Dhabi, Sharjah).
        brand: Vehicle brand or 'any' for all-makes centres.
    """
    city_l = city.lower()
    matches = [c for c in SERVICE_CENTERS if city_l in c["city"].lower()]
    if brand.lower() != "any":
        matches = [c for c in matches if brand.lower() in c["brands"].lower() or c["brands"] == "All makes"]
    if not matches:
        return f"No service centre found in {city} for {brand}. Try Dubai or Abu Dhabi."
    lines = [f"Service centres in {city}:"]
    for c in matches:
        lines.append(f"  - {c['name']} ({c['brands']})")
    return "\n".join(lines)


@tool
def check_appointment_availability(service_type: str, preferred_date: str) -> str:
    """Check available appointment slots for a service near a preferred date."""
    try:
        base = datetime.strptime(preferred_date, "%Y-%m-%d")
    except ValueError:
        base = datetime.now()
    slots = []
    for offset, time in [(0, "09:00"), (1, "11:30"), (2, "14:00")]:
        slot_date = (base + timedelta(days=offset)).strftime("%Y-%m-%d")
        slots.append(f"{slot_date} at {time}")
    return (
        f"Available {service_type} slots near {preferred_date}:\n"
        + "\n".join(f"  - {s}" for s in slots)
    )


def _vehicle_from_context(thread_id: str) -> str:
    ctx = get_thread_context(thread_id)
    if ctx.get("vehicle"):
        return str(ctx["vehicle"])
    phone = ctx.get("customer_phone")
    if phone:
        profile = get_customer_by_phone(phone)
        if profile and profile.get("vehicles"):
            v = profile["vehicles"][0]
            return f"{v['year']} {v['make']} {v['model']}"
    return "Vehicle not specified"


@tool
def book_appointment(
    service_type: str,
    date: str,
    time: str,
    customer_name: str,
    vehicle_model: str = "",
) -> str:
    """Book a service appointment and return a confirmation code.

    Args:
        service_type: Type of service to book.
        date: Appointment date (YYYY-MM-DD).
        time: Appointment time (HH:MM).
        customer_name: Customer full name.
        vehicle_model: Vehicle as one string, e.g. "2020 Toyota Camry".
    """
    vehicle = vehicle_model.strip() or _vehicle_from_context(_current_thread_id)
    confirmation_code = f"AF-{uuid.uuid4().hex[:8].upper()}"
    log_booking(confirmation_code, service_type, date, time, customer_name, vehicle, _current_thread_id)
    log_tool_event(_current_thread_id, "book_appointment")
    return (
        f"Appointment confirmed!\n"
        f"Confirmation code: {confirmation_code}\n"
        f"Service: {service_type}\n"
        f"Date: {date} at {time}\n"
        f"Customer: {customer_name}\n"
        f"Vehicle: {vehicle}"
    )


@tool
def lookup_vehicle_recall(make: str, model: str, year: int) -> str:
    """Look up open safety recalls for a vehicle."""
    key = (make.lower(), model.lower(), year)
    recalls = RECALL_DATA.get(key)
    log_tool_event(_current_thread_id, "lookup_vehicle_recall")
    if recalls is None:
        return (
            f"No recall data on file for {year} {make} {model}. "
            "This does not guarantee the vehicle has no recalls."
        )
    if not recalls:
        return f"No open recalls found for {year} {make} {model}."
    lines = [f"Open recalls for {year} {make} {model}:"]
    for r in recalls:
        lines.append(f"  - [{r['recall_id']}] {r['description']} (status: {r['status']})")
    return "\n".join(lines)


def _parse_mileage_km(mileage: int | str) -> int:
    """Convert exact km or approximate range labels to a single km estimate."""
    if isinstance(mileage, int):
        return max(0, mileage)
    s = str(mileage).lower().replace(",", "")
    if "under" in s and "40" in s:
        return 20_000
    if "over" in s and "120" in s:
        return 150_000
    parts = [int(n) for n in re.findall(r"\d+", s)]
    if len(parts) >= 2:
        return (parts[0] + parts[1]) // 2
    if parts:
        return parts[0]
    return 60_000


@tool
def get_trade_in_quote(make: str, model: str, year: int, mileage: int | str, condition: str) -> str:
    """Get an estimated trade-in value for a vehicle.

    mileage may be an integer (km) or an approximate range such as '40,000 – 80,000 km'.
    """
    mileage_km = _parse_mileage_km(mileage)
    current_year = datetime.now().year
    age = max(0, current_year - year)
    base_value = max(3000, 28000 - age * 1800)
    multiplier = CONDITION_MULTIPLIERS.get(condition.lower(), 0.75)
    mileage_penalty = max(0, (mileage_km - 60000) * 0.08)
    estimate = max(500, base_value * multiplier - mileage_penalty)
    log_tool_event(_current_thread_id, "get_trade_in_quote")
    mileage_label = f"{mileage_km:,} km" if isinstance(mileage, int) else str(mileage)
    return (
        f"Estimated trade-in for {year} {make} {model}:\n"
        f"  Condition: {condition}\n"
        f"  Mileage: {mileage_label}\n"
        f"  Estimated value: ${estimate:,.0f}\n"
        f"(Estimate only — final offer requires in-person inspection.)"
    )


@tool
def request_test_drive(brand: str, model: str, preferred_date: str, customer_name: str) -> str:
    """Request a test drive for a vehicle."""
    request_id = f"TD-{uuid.uuid4().hex[:8].upper()}"
    log_tool_event(_current_thread_id, "request_test_drive")
    return (
        f"Test drive request received!\n"
        f"Request ID: {request_id}\n"
        f"Vehicle: {brand} {model}\n"
        f"Preferred date: {preferred_date}\n"
        f"Customer: {customer_name}\n"
        f"A sales advisor will confirm your slot shortly."
    )


@tool
def escalate_to_human(reason: str, conversation_summary: str) -> str:
    """Escalate the conversation to a human agent with a full handover summary."""
    tid = _current_thread_id
    ctx = get_thread_context(tid)
    customer = None
    if ctx.get("customer_phone"):
        customer = get_customer_by_phone(ctx["customer_phone"])
    package = build_handover_package(
        tid,
        reason,
        conversation_summary,
        customer=customer,
        routed_agent=ctx.get("routed_agent"),
    )
    handover_id = log_escalation(tid, reason, conversation_summary, handover_package=package)
    return (
        f"Escalation logged — ticket {package['ticket_id']} (handover #{handover_id}).\n"
        f"An Al Futtaim service advisor will follow up shortly.\n"
        f"Reason: {reason}"
    )


SERVICE_TOOLS = [
    get_customer_profile,
    find_service_center,
    check_appointment_availability,
    book_appointment,
    escalate_to_human,
]

SALES_TOOLS = [
    get_customer_profile,
    get_trade_in_quote,
    request_test_drive,
    escalate_to_human,
]

RECALL_TOOLS = [
    get_customer_profile,
    lookup_vehicle_recall,
    escalate_to_human,
]

HANDOVER_TOOLS = [escalate_to_human]

GENERAL_TOOLS = [
    get_customer_profile,
    find_service_center,
    escalate_to_human,
]

ALL_TOOLS = [
    get_customer_profile,
    find_service_center,
    check_appointment_availability,
    book_appointment,
    lookup_vehicle_recall,
    get_trade_in_quote,
    request_test_drive,
    escalate_to_human,
]
