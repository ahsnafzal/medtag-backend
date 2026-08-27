"""
Shared call queue / busy state for video consultations.

Used by REST views (reliable request–response) and WebSocket consumers (presence).
All mutations run under one lock so HTTP and Channels stay consistent.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


_lock = threading.RLock()
_user_counts: dict[int, int] = {}
_doctor_states: dict[int, dict[str, Any]] = {}
_doctor_watchers: dict[int, set[int]] = defaultdict(set)
_patient_watchers: dict[int, set[int]] = defaultdict(set)


def default_doctor_state() -> dict[str, Any]:
    return {
        "busy": False,
        "current_appointment_id": None,
        "current_patient_id": None,
        "queue": [],
    }


def user_connect(user_id: int) -> None:
    with _lock:
        _user_counts[user_id] = _user_counts.get(user_id, 0) + 1


def user_disconnect(user_id: int, *, role: str | None = None) -> None:
    with _lock:
        _user_counts[user_id] = max(0, _user_counts.get(user_id, 0) - 1)
        if _user_counts[user_id] == 0:
            _user_counts.pop(user_id, None)
        if role == "doctor":
            state = _doctor_states.setdefault(user_id, default_doctor_state())
            state["busy"] = False
            state["current_appointment_id"] = None
            state["current_patient_id"] = None


def doctor_online(doctor_user_id: int) -> bool:
    with _lock:
        return _user_counts.get(doctor_user_id, 0) > 0


def patient_online(patient_user_id: int) -> bool:
    with _lock:
        return _user_counts.get(patient_user_id, 0) > 0


def set_monitored_doctors(patient_user_id: int, doctor_ids: set[int]) -> None:
    with _lock:
        for did in list(_doctor_watchers.keys()):
            _doctor_watchers[did].discard(patient_user_id)
        for did in doctor_ids:
            _doctor_watchers[did].add(patient_user_id)


def set_monitored_patients(doctor_user_id: int, patient_ids: set[int]) -> None:
    with _lock:
        for pid in list(_patient_watchers.keys()):
            _patient_watchers[pid].discard(doctor_user_id)
        for pid in patient_ids:
            _patient_watchers[pid].add(doctor_user_id)


def mark_doctor_in_call(doctor_user_id: int, appointment_id: int) -> dict[str, Any]:
    """Called from call-room WebSocket when doctor sends ringing."""
    with _lock:
        state = _doctor_states.setdefault(doctor_user_id, default_doctor_state())
        state["busy"] = True
        state["current_appointment_id"] = int(appointment_id)
    return doctor_presence_payload(doctor_user_id)


def doctor_presence_payload(doctor_id: int) -> dict[str, Any]:
    with _lock:
        state = _doctor_states.get(doctor_id)
        if state is None:
            state = default_doctor_state()
        online = _user_counts.get(doctor_id, 0) > 0
        busy = bool(state.get("busy"))
        queue = state.get("queue") or []
        cur = state.get("current_appointment_id")
    return {
        "type": "doctor_presence_update",
        "doctor_id": doctor_id,
        "is_online": online,
        "is_busy": busy,
        "is_free": online and not busy,
        "queue_length": len(queue),
        "current_appointment_id": cur,
    }


def watchers_for_doctor(doctor_id: int) -> set[int]:
    with _lock:
        return set(_doctor_watchers.get(doctor_id, set()))


def watchers_for_patient(patient_id: int) -> set[int]:
    with _lock:
        return set(_patient_watchers.get(patient_id, set()))


def reserve_call_slot(
    *,
    doctor_id: int,
    appointment_id: int,
    patient_id: int | None,
    patient_name: str,
    actor_role: str,
    auth_user_id: int,
) -> dict[str, Any]:
    """
    Returns dict with:
      - requester_payload: sent to the caller (HTTP body or WS)
      - doctor_event: optional push to doctor's notification channel
      - doctor_queue_payload: push to doctor
      - presence_targets: list of (user_id, payload) for doctor_presence_update
    """
    doctor_event = None

    try:
        doctor_id = int(doctor_id)
        appointment_id = int(appointment_id)
        auth_user_id = int(auth_user_id)
        if patient_id is not None:
            patient_id = int(patient_id)
    except (TypeError, ValueError):
        return {"error": "bad_ids", "detail": "Invalid appointment or doctor id."}

    with _lock:
        state = _doctor_states.setdefault(doctor_id, default_doctor_state())
        online = _user_counts.get(doctor_id, 0) > 0

        if actor_role == "patient":
            patient_id = auth_user_id
        elif actor_role == "doctor":
            if doctor_id != auth_user_id:
                return {"error": "doctor_mismatch", "detail": "Invalid doctor for this session."}
        else:
            return {"error": "bad_role", "detail": "actor_role must be patient or doctor."}

        current_appt = state.get("current_appointment_id")
        try:
            current_appt = int(current_appt) if current_appt is not None else None
        except (TypeError, ValueError):
            current_appt = None

        if not online:
            requester_payload = {
                "type": "call_slot_response",
                "status": "offline",
                "doctor_id": doctor_id,
                "appointment_id": appointment_id,
                "message": "Doctor is offline right now.",
            }
        elif state["busy"] and current_appt != appointment_id:
            existing_idx = None
            queue = state.setdefault("queue", [])
            for idx, queued_item in enumerate(queue):
                try:
                    qid = int(queued_item.get("appointment_id"))
                except (TypeError, ValueError):
                    continue
                if qid == appointment_id:
                    existing_idx = idx
                    break

            if existing_idx is None:
                queue.append(
                    {
                        "appointment_id": appointment_id,
                        "patient_id": patient_id,
                        "patient_name": patient_name,
                        "requested_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                queue_position = len(queue)
            else:
                queue_position = existing_idx + 1

            requester_payload = {
                "type": "call_slot_response",
                "status": "queued",
                "reason": "doctor_busy",
                "doctor_id": doctor_id,
                "appointment_id": appointment_id,
                "queue_position": queue_position,
                "current_appointment_id": current_appt,
                "message": (
                    "The doctor is currently in a video call with another patient. "
                    f"You are in queue position #{queue_position}. "
                    "We will notify you when they are free."
                ),
            }
        else:
            state["busy"] = True
            state["current_appointment_id"] = appointment_id
            state["current_patient_id"] = patient_id
            filtered_queue = []
            for item in state.setdefault("queue", []):
                try:
                    q_appt = int(item.get("appointment_id"))
                except (TypeError, ValueError):
                    filtered_queue.append(item)
                    continue
                if q_appt != appointment_id:
                    filtered_queue.append(item)
            state["queue"] = filtered_queue

            requester_payload = {
                "type": "call_slot_response",
                "status": "granted",
                "doctor_id": doctor_id,
                "appointment_id": appointment_id,
                "message": "Call slot granted.",
            }
            if actor_role == "patient":
                doctor_event = {
                    "type": "incoming_call_request",
                    "doctor_id": doctor_id,
                    "appointment_id": appointment_id,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                }

        queue_length = len(state.get("queue", []))

    presence = doctor_presence_payload(doctor_id)
    targets = watchers_for_doctor(doctor_id) | {doctor_id}

    doctor_queue_payload = {
        "type": "doctor_queue_update",
        "doctor_id": doctor_id,
        "queue_length": queue_length,
    }

    return {
        "requester_payload": requester_payload,
        "doctor_event": doctor_event,
        "doctor_queue_payload": doctor_queue_payload,
        "presence_payload": presence,
        "presence_targets": targets,
        "doctor_id": doctor_id,
    }


def release_call_slot(*, doctor_id: int, appointment_id: int) -> dict[str, Any]:
    """End active slot; optionally promote queue. Returns payloads to push via channel layer."""
    try:
        appointment_id = int(appointment_id)
        doctor_id = int(doctor_id)
    except (TypeError, ValueError):
        return {"error": "bad_ids"}

    with _lock:
        state = _doctor_states.setdefault(doctor_id, default_doctor_state())

        next_queued = None
        cur = state.get("current_appointment_id")
        try:
            cur = int(cur) if cur is not None else None
        except (TypeError, ValueError):
            cur = None

        if cur == appointment_id:
            state["busy"] = False
            state["current_appointment_id"] = None
            state["current_patient_id"] = None

        if not state["busy"] and state.get("queue"):
            next_queued = state["queue"].pop(0)
            state["busy"] = True
            state["current_appointment_id"] = next_queued.get("appointment_id")
            state["current_patient_id"] = next_queued.get("patient_id")

        queue_length = len(state.get("queue", []))

    out: dict[str, Any] = {
        "doctor_queue_payload": {
            "type": "doctor_queue_update",
            "doctor_id": doctor_id,
            "queue_length": queue_length,
        },
        "presence_payload": doctor_presence_payload(doctor_id),
        "presence_targets": watchers_for_doctor(doctor_id) | {doctor_id},
    }

    if next_queued:
        npid = next_queued.get("patient_id")
        out["queue_ready"] = {
            "user_id": int(npid) if npid is not None else None,
            "payload": {
                "type": "call_queue_ready",
                "doctor_id": doctor_id,
                "appointment_id": next_queued.get("appointment_id"),
                "message": "Doctor is free now. You can join the call.",
            },
        }
        out["doctor_queue_payload"]["next_appointment_id"] = next_queued.get("appointment_id")
        out["doctor_queue_payload"]["next_patient_name"] = next_queued.get("patient_name")

    return out
