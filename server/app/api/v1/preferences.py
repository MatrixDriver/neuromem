"""Preferences API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.api.v1.schemas import (
    PreferenceDeleteResponse,
    PreferenceListResponse,
    PreferenceResponse,
    PreferenceSet,
)
from server.app.core.logging import get_logger
from server.app.db.session import get_db
from server.app.services.auth import AuthContext, get_auth_context
from server.app.services.preferences import (
    delete_preference,
    get_preference,
    list_preferences,
    set_preference,
)

router = APIRouter(prefix="/preferences", tags=["preferences"])
logger = get_logger(__name__)


@router.post("", response_model=PreferenceResponse)
async def set_pref(
    body: PreferenceSet,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Set a user preference (upsert).

    Creates a new preference or updates existing one if the key already exists.

    Returns:
        PreferenceResponse: The created or updated preference

    Raises:
        HTTPException 401: Invalid or missing API key
        HTTPException 500: Database error
    """
    try:
        pref = await set_preference(
            db, auth.tenant_id, body.user_id, body.key, body.value, body.metadata
        )
        logger.info(
            "Preference set",
            extra={
                "user_id": body.user_id,
                "key": body.key,
                "tenant_id": str(auth.tenant_id)
            }
        )
        return PreferenceResponse(
            user_id=body.user_id,
            key=pref.key,
            value=pref.value,
            metadata=pref.metadata_,
            created_at=pref.created_at,
            updated_at=pref.updated_at,
        )
    except Exception as e:
        logger.error(
            f"Failed to set preference: {str(e)}",
            extra={"user_id": body.user_id, "key": body.key}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set preference: {str(e)}"
        )


@router.get("", response_model=PreferenceListResponse)
async def list_prefs(
    user_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    List all preferences for a user.

    Returns:
        PreferenceListResponse: List of all preferences for the user

    Raises:
        HTTPException 401: Invalid or missing API key
    """
    prefs = await list_preferences(db, auth.tenant_id, user_id)
    return PreferenceListResponse(
        user_id=user_id,
        preferences=[
            PreferenceResponse(
                user_id=user_id,
                key=p.key,
                value=p.value,
                metadata=p.metadata_,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in prefs
        ],
    )


@router.get("/{key}", response_model=PreferenceResponse)
async def get_pref(
    key: str,
    user_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single preference by key.

    Returns:
        PreferenceResponse: The requested preference

    Raises:
        HTTPException 401: Invalid or missing API key
        HTTPException 404: Preference not found
    """
    pref = await get_preference(db, auth.tenant_id, user_id, key)
    if not pref:
        raise HTTPException(
            status_code=404,
            detail=f"Preference '{key}' not found for user '{user_id}'"
        )
    return PreferenceResponse(
        user_id=user_id,
        key=pref.key,
        value=pref.value,
        metadata=pref.metadata_,
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )


@router.delete("/{key}", response_model=PreferenceDeleteResponse)
async def delete_pref(
    key: str,
    user_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a preference.

    Returns:
        PreferenceDeleteResponse: Deletion confirmation

    Raises:
        HTTPException 401: Invalid or missing API key
        HTTPException 404: Preference not found
    """
    deleted = await delete_preference(db, auth.tenant_id, user_id, key)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Preference '{key}' not found for user '{user_id}'"
        )
    return PreferenceDeleteResponse(deleted=True)
