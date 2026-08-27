# accounts/consumers.py
import json

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

from . import call_session
from .models import Appointment


@database_sync_to_async
def _get_doctor_user_id_for_appointment(appointment_id):
    try:
        apt = Appointment.objects.select_related("doctor__user").get(id=appointment_id)
        return apt.doctor.user_id
    except Appointment.DoesNotExist:
        return None


async def _fan_out_doctor_presence_ws(doctor_id):
    payload = await sync_to_async(call_session.doctor_presence_payload)(doctor_id)
    watchers = await sync_to_async(call_session.watchers_for_doctor)(doctor_id)
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    for uid in watchers | {int(doctor_id)}:
        await channel_layer.group_send(
            f"notifications_{uid}",
            {"type": "notification_message", "message": payload},
        )


class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.appointment_id = self.scope["url_route"]["kwargs"]["appointment_id"]
        self.room_group_name = f"call_{self.appointment_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "call_signal", "message": data},
        )

        status = data.get("status")
        if status == "ringing":
            try:
                apt_id = int(self.appointment_id)
            except (TypeError, ValueError):
                return
            doctor_uid = await _get_doctor_user_id_for_appointment(apt_id)
            if doctor_uid:
                await sync_to_async(call_session.mark_doctor_in_call)(doctor_uid, apt_id)
                await _fan_out_doctor_presence_ws(doctor_uid)

    async def call_signal(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps(message))


class NotificationConsumer(AsyncWebsocketConsumer):
    """Realtime watches / presence only. Call-slot reserve/release use REST APIs."""

    async def _notify_user_direct_or_group(self, user_id, payload):
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return
        if uid == self.auth_user_id:
            await self.send(text_data=json.dumps(payload))
            return
        await self.channel_layer.group_send(
            f"notifications_{uid}",
            {"type": "notification_message", "message": payload},
        )

    async def _push_doctor_presence(self, doctor_id):
        payload = await sync_to_async(call_session.doctor_presence_payload)(doctor_id)
        watchers = await sync_to_async(call_session.watchers_for_doctor)(doctor_id)
        for uid in watchers | {int(doctor_id)}:
            await self._notify_user_direct_or_group(uid, payload)

    async def _push_patient_presence(self, patient_id, is_online):
        watchers = await sync_to_async(call_session.watchers_for_patient)(patient_id)
        payload = {
            "type": "patient_presence_update",
            "patient_id": int(patient_id),
            "is_online": bool(is_online),
        }
        for uid in watchers:
            await self._notify_user_direct_or_group(uid, payload)

    async def _handle_monitor_doctors(self, payload):
        self.auth_role = "patient"
        doctor_ids = payload.get("doctor_ids") or []
        if not isinstance(doctor_ids, list):
            return

        try:
            normalized = {int(doc_id) for doc_id in doctor_ids}
        except (TypeError, ValueError):
            return

        await sync_to_async(call_session.set_monitored_doctors)(self.auth_user_id, normalized)
        for doc_id in normalized:
            await self._push_doctor_presence(doc_id)

    async def _handle_monitor_patients(self, payload):
        self.auth_role = "doctor"
        patient_ids = payload.get("patient_ids") or []
        if not isinstance(patient_ids, list):
            return

        try:
            normalized = {int(patient_id) for patient_id in patient_ids}
        except (TypeError, ValueError):
            return

        await sync_to_async(call_session.set_monitored_patients)(self.auth_user_id, normalized)
        for pid in normalized:
            online = await sync_to_async(call_session.patient_online)(pid)
            await self._notify_user_direct_or_group(
                self.auth_user_id,
                {
                    "type": "patient_presence_update",
                    "patient_id": pid,
                    "is_online": online,
                },
            )

    async def _handle_register_presence(self, payload):
        requested_role = payload.get("role")
        if requested_role not in {"patient", "doctor"}:
            return

        self.auth_role = requested_role
        if self.auth_role == "doctor":
            await self._push_doctor_presence(self.auth_user_id)
        else:
            await self._push_patient_presence(self.auth_user_id, True)

    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.room_group_name = f"notifications_{self.user_id}"

        try:
            self.auth_user_id = int(self.user_id)
        except (TypeError, ValueError):
            await self.close(code=4000)
            return

        self.auth_role = "unknown"
        user = self.scope.get("user")
        if user and getattr(user, "is_authenticated", False) and int(user.id) == self.auth_user_id:
            self.auth_role = "doctor" if getattr(user, "user_type", None) == "doctor" else "patient"

        await sync_to_async(call_session.user_connect)(self.auth_user_id)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        if self.auth_role == "doctor":
            await self._push_doctor_presence(self.auth_user_id)
        elif self.auth_role == "patient":
            await self._push_patient_presence(self.auth_user_id, True)

    async def disconnect(self, close_code):
        if not hasattr(self, "auth_user_id"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            return

        role = self.auth_role if self.auth_role in ("doctor", "patient") else None
        await sync_to_async(call_session.user_disconnect)(self.auth_user_id, role=role)

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        if role == "doctor":
            await self._push_doctor_presence(self.auth_user_id)
        elif role == "patient":
            await self._push_patient_presence(self.auth_user_id, False)

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return

        action = payload.get("action")
        if action == "register_presence":
            await self._handle_register_presence(payload)
        elif action == "monitor_doctors":
            await self._handle_monitor_doctors(payload)
        elif action == "monitor_patients":
            await self._handle_monitor_patients(payload)

    async def notification_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))
