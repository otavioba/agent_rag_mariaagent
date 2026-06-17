from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .agent import ask_agent
from .config import Settings, get_settings
from .database import (
    fetch_evolution_instance_state,
    fetch_evolution_instance_state_by_name,
    init_database,
    list_evolution_instance_states,
    register_processed_evolution_message,
    upsert_evolution_instance_state,
)
from .evolution import (
    EvolutionGoClient,
    build_whatsapp_conversation_id,
    extract_text_from_message_data,
    is_group_jid,
    is_newsletter_jid,
    normalize_whatsapp_jid,
)
from .guardrails import GuardrailViolation
from .vectorstore import ensure_vector_store_ready


class AskRequest(BaseModel):
    question: str
    conversation_id: str | None = None
    user_id: str = "default-user"
    store_id: str | None = None


class EvolutionCreateInstanceRequest(BaseModel):
    instance_name: str | None = None
    integration: str = "WHATSAPP-BAILEYS"


class EvolutionConnectInstanceRequest(BaseModel):
    instance_id: str | None = None
    subscribe: list[str] | None = None
    immediate: bool = True
    phone: str | None = None
    webhook_url: str | None = None


class EvolutionSendTextRequest(BaseModel):
    number: str
    text: str = Field(min_length=1)
    instance_name: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_database(settings)
    yield


app = FastAPI(
    title="Maria RAG Agent API",
    version="0.1.0",
    lifespan=lifespan,
)


def _settings() -> Settings:
    return get_settings()


def _serialize_instance_row(row) -> dict[str, Any]:
    payload = dict(row)
    metadata_json = payload.get("metadata_json")
    if metadata_json:
        try:
            payload["metadata"] = json.loads(metadata_json)
        except json.JSONDecodeError:
            payload["metadata"] = {"raw": metadata_json}
    else:
        payload["metadata"] = None
    payload.pop("metadata_json", None)
    return payload


def _resolve_instance_name(settings: Settings, instance_id: str | None = None) -> str:
    if instance_id:
        row = fetch_evolution_instance_state(settings, instance_id)
        if row and row["instance_name"]:
            return str(row["instance_name"])
    return settings.evolution_instance_name


def _resolve_instance_send_credentials(
    settings: Settings,
    instance_id: str | None = None,
    instance_name: str | None = None,
) -> tuple[str, str | None, str | None]:
    row = None
    if instance_id:
        row = fetch_evolution_instance_state(settings, instance_id)
    elif instance_name:
        row = fetch_evolution_instance_state_by_name(settings, instance_name)

    resolved_name = (
        str(row["instance_name"])
        if row and row.get("instance_name")
        else (instance_name or settings.evolution_instance_name)
    )
    resolved_id = str(row["instance_id"]) if row and row.get("instance_id") else instance_id
    instance_token = str(row["instance_token"]) if row and row.get("instance_token") else None
    return resolved_name, resolved_id, instance_token


def _resolve_instance_id(settings: Settings, explicit_instance_id: str | None = None) -> str:
    if explicit_instance_id:
        return explicit_instance_id
    if settings.evolution_instance_id:
        return settings.evolution_instance_id

    row = fetch_evolution_instance_state_by_name(settings, settings.evolution_instance_name)
    if row and row["instance_id"]:
        return str(row["instance_id"])

    raise HTTPException(
        status_code=400,
        detail=(
            "Nenhum instance_id foi informado. Crie uma instancia primeiro ou configure "
            "EVOLUTION_INSTANCE_ID."
        ),
    )


def _store_instance_state_from_event(
    settings: Settings,
    instance_id: str,
    instance_token: str | None,
    event: str,
    data: dict[str, Any],
) -> None:
    status = None
    qr_code_base64 = None
    phone_jid = None
    push_name = None

    if event == "QRCode":
        qr_code_base64 = data.get("qrcode")
        status = "awaiting_scan"
    elif event == "PairSuccess":
        status = data.get("status")
        phone_jid = data.get("jid") or data.get("ID")
        push_name = data.get("pushName") or data.get("BusinessName")
    elif event == "Connected":
        status = data.get("status", "open")
        phone_jid = data.get("jid")
        push_name = data.get("pushName")
        qr_code_base64 = ""
    elif event == "LoggedOut":
        status = data.get("Reason", "logged_out")
        qr_code_base64 = ""
    elif event == "OfflineSyncCompleted":
        status = "synced"
    elif event == "Message":
        info = data.get("Info") if isinstance(data.get("Info"), dict) else {}
        status = "open"
        phone_jid = info.get("Sender")
        push_name = info.get("PushName")

    upsert_evolution_instance_state(
        settings=settings,
        instance_id=instance_id,
        instance_name=settings.evolution_instance_name,
        instance_token=instance_token,
        last_event=event,
        connection_status=status,
        qr_code_base64=qr_code_base64,
        phone_jid=phone_jid,
        push_name=push_name,
        metadata=data,
    )


def _build_media_fallback_text(data: dict[str, Any]) -> str:
    info = data.get("Info") if isinstance(data.get("Info"), dict) else {}
    media_type = info.get("MediaType") or "midia"
    return (
        "Recebi sua mensagem em formato de "
        f"{media_type}, mas por enquanto consigo responder apenas texto. "
        "Se puder, me envie sua pergunta digitada."
    )


@app.get("/health")
def health() -> dict[str, Any]:
    settings = _settings()
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "api_port": settings.api_port,
        "evolution_enabled": settings.evolution_enabled,
    }


@app.post("/api/ask")
def ask(request: AskRequest) -> dict[str, Any]:
    settings = _settings()
    ensure_vector_store_ready(settings)
    reply = ask_agent(
        question=request.question,
        settings=settings,
        conversation_id=request.conversation_id,
        user_id=request.user_id,
        store_id=request.store_id,
    )
    return {
        "answer": reply.answer,
        "conversation_id": reply.conversation_id,
        "user_id": reply.user_id,
        "store_id": reply.store_id,
    }


@app.get("/api/evolution/health")
def evolution_health() -> dict[str, Any]:
    settings = _settings()
    if not settings.evolution_enabled:
        raise HTTPException(status_code=400, detail="Evolution Go integration is disabled.")
    return EvolutionGoClient(settings).health()


@app.get("/api/evolution/instances")
def evolution_instances() -> dict[str, Any]:
    settings = _settings()
    rows = list_evolution_instance_states(settings)
    return {"items": [_serialize_instance_row(row) for row in rows]}


@app.post("/api/evolution/instances/create")
def evolution_create_instance(request: EvolutionCreateInstanceRequest) -> dict[str, Any]:
    settings = _settings()
    if not settings.evolution_enabled:
        raise HTTPException(status_code=400, detail="Evolution Go integration is disabled.")

    instance_name = request.instance_name or settings.evolution_instance_name
    response = EvolutionGoClient(settings).create_instance(
        instance_name=instance_name,
        integration=request.integration,
    )

    instance_payload = response.get("instance", response)
    instance_id = instance_payload.get("instanceId")
    instance_token = instance_payload.get("token")
    status = instance_payload.get("status")

    if instance_id:
        upsert_evolution_instance_state(
            settings=settings,
            instance_id=str(instance_id),
            instance_name=instance_name,
            instance_token=str(instance_token) if instance_token else None,
            last_event="CreateInstance",
            connection_status=str(status) if status else "created",
            metadata=response,
        )

    return response


@app.post("/api/evolution/instances/connect")
def evolution_connect_instance(request: EvolutionConnectInstanceRequest) -> dict[str, Any]:
    settings = _settings()
    if not settings.evolution_enabled:
        raise HTTPException(status_code=400, detail="Evolution Go integration is disabled.")

    instance_id = _resolve_instance_id(settings, request.instance_id)
    subscribe = request.subscribe or settings.evolution_subscribe_event_list
    response = EvolutionGoClient(settings).connect_instance(
        instance_id=instance_id,
        subscribe=subscribe,
        immediate=request.immediate,
        phone=request.phone,
        webhook_url=(
            request.webhook_url
            or settings.evolution_public_webhook_url
            or settings.evolution_internal_webhook_url
        ),
    )

    upsert_evolution_instance_state(
        settings=settings,
        instance_id=instance_id,
        instance_name=_resolve_instance_name(settings, instance_id),
        last_event="ConnectInstance",
        connection_status="connecting",
        metadata=response,
    )
    return response


@app.post("/api/evolution/messages/test")
def evolution_send_test_message(request: EvolutionSendTextRequest) -> dict[str, Any]:
    settings = _settings()
    if not settings.evolution_enabled:
        raise HTTPException(status_code=400, detail="Evolution Go integration is disabled.")
    instance_name, instance_id, instance_token = _resolve_instance_send_credentials(
        settings=settings,
        instance_name=request.instance_name,
    )
    return EvolutionGoClient(settings).send_text(
        number=request.number,
        text=request.text,
        instance_name=instance_name,
        instance_id=instance_id,
        api_key_override=instance_token,
    )


@app.post("/webhooks/evolution")
def evolution_webhook(
    payload: dict[str, Any],
    request: Request,
    x_webhook_secret: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> dict[str, Any]:
    settings = _settings()

    if settings.evolution_webhook_secret:
        received_secret = token or x_webhook_secret
        if received_secret != settings.evolution_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    event = payload.get("event")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    instance_id = payload.get("instanceId")
    instance_token = payload.get("instanceToken")

    if not event or not instance_id:
        raise HTTPException(status_code=400, detail="Webhook payload is missing required fields.")

    _store_instance_state_from_event(
        settings=settings,
        instance_id=str(instance_id),
        instance_token=str(instance_token) if instance_token else None,
        event=str(event),
        data=data,
    )

    if event != "Message":
        return {"received": True, "event": event}

    info = data.get("Info") if isinstance(data.get("Info"), dict) else {}
    if info.get("IsFromMe"):
        return {"received": True, "ignored": "from_me"}

    chat_jid = info.get("Chat")
    sender_jid = info.get("Sender")
    message_id = info.get("ID")

    if settings.evolution_ignore_group_messages and (
        bool(info.get("IsGroup")) or is_group_jid(chat_jid) or is_group_jid(sender_jid)
    ):
        return {"received": True, "ignored": "group"}

    if settings.evolution_ignore_newsletter_messages and (
        is_newsletter_jid(chat_jid) or is_newsletter_jid(sender_jid)
    ):
        return {"received": True, "ignored": "newsletter"}

    sender_number = normalize_whatsapp_jid(sender_jid)
    if not sender_number:
        return {"received": True, "ignored": "missing_sender"}

    if message_id and not register_processed_evolution_message(
        settings=settings,
        instance_id=str(instance_id),
        message_id=str(message_id),
    ):
        return {"received": True, "ignored": "duplicate_message"}

    text = extract_text_from_message_data(data)
    if not text:
        if not settings.evolution_reply_to_media_without_text:
            return {"received": True, "ignored": "no_text"}
        fallback_text = _build_media_fallback_text(data)
        instance_name, resolved_instance_id, instance_token = _resolve_instance_send_credentials(
            settings=settings,
            instance_id=str(instance_id),
        )
        EvolutionGoClient(settings).send_text(
            number=sender_number,
            text=fallback_text,
            instance_name=instance_name,
            instance_id=resolved_instance_id,
            api_key_override=instance_token,
        )
        return {
            "received": True,
            "reply_sent": True,
            "conversation_id": None,
            "event": event,
            "path": str(request.url.path),
            "mode": "media_fallback",
        }

    try:
        ensure_vector_store_ready(settings)
        reply = ask_agent(
            question=text,
            settings=settings,
            conversation_id=build_whatsapp_conversation_id(str(instance_id), sender_number),
            user_id=f"wa:{sender_number}",
            store_id=settings.evolution_default_store_id,
        )
        reply_text = reply.answer
        conversation_id = reply.conversation_id
    except GuardrailViolation as exc:
        reply_text = str(exc)
        conversation_id = None

    instance_name, resolved_instance_id, instance_token = _resolve_instance_send_credentials(
        settings=settings,
        instance_id=str(instance_id),
    )
    EvolutionGoClient(settings).send_text(
        number=sender_number,
        text=reply_text,
        instance_name=instance_name,
        instance_id=resolved_instance_id,
        api_key_override=instance_token,
    )

    return {
        "received": True,
        "reply_sent": True,
        "conversation_id": conversation_id,
        "event": event,
        "path": str(request.url.path),
    }


def main() -> None:
    settings = _settings()
    uvicorn.run(
        "maria_rag_agent.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
