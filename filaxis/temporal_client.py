"""Shared Temporal client factory.

Supports both local (no TLS) and Temporal Cloud (TLS + API key).

Local dev:
  TEMPORAL_HOST=localhost:7233
  TEMPORAL_TLS=false

Temporal Cloud:
  TEMPORAL_HOST=<namespace>.<account-id>.tmprl.cloud:7233
  TEMPORAL_NAMESPACE=<namespace>.<account-id>
  TEMPORAL_API_KEY=<api-key>
  TEMPORAL_TLS=true
"""

from temporalio.client import Client

from filaxis.config import settings
from filaxis.logging import get_logger

log = get_logger(__name__)


async def get_temporal_client() -> Client:
    kwargs: dict = {
        "target_host": settings.temporal_host,
        "namespace": settings.temporal_namespace,
    }

    if settings.temporal_api_key:
        kwargs["api_key"] = settings.temporal_api_key
        kwargs["tls"] = True
        log.info("temporal_client.connecting", mode="cloud", host=settings.temporal_host)
    elif settings.temporal_tls:
        kwargs["tls"] = True
        log.info("temporal_client.connecting", mode="tls", host=settings.temporal_host)
    else:
        log.info("temporal_client.connecting", mode="local", host=settings.temporal_host)

    return await Client.connect(**kwargs)
