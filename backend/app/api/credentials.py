from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.credential import Credential
from app.models.user import User
from app.schemas.credential import CredentialCreate, CredentialUpdate, CredentialResponse
from app.services.credential_service import encrypt
from app.api.deps import get_current_user

router = APIRouter(prefix="/credentials", tags=["credentials"], dependencies=[Depends(get_current_user)])


def _to_response(c: Credential) -> CredentialResponse:
    return CredentialResponse(
        id=c.id,
        name=c.name,
        type=c.type,
        username=c.username,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat(),
    )


@router.get("", response_model=list[CredentialResponse])
async def list_credentials(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Credential).order_by(Credential.name))
    return [_to_response(c) for c in result.scalars().all()]


@router.post("", response_model=CredentialResponse, status_code=201)
async def create_credential(body: CredentialCreate, db: AsyncSession = Depends(get_db)):
    cred = Credential(
        name=body.name,
        type=body.type,
        username=body.username,
        encrypted_password=encrypt(body.password) if body.password else None,
        encrypted_private_key=encrypt(body.private_key) if body.private_key else None,
        encrypted_passphrase=encrypt(body.passphrase) if body.passphrase else None,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return _to_response(cred)


@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(credential_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    return _to_response(cred)


@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: str, body: CredentialUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    if body.name is not None:
        cred.name = body.name
    if body.username is not None:
        cred.username = body.username
    if body.password is not None:
        cred.encrypted_password = encrypt(body.password)
    if body.private_key is not None:
        cred.encrypted_private_key = encrypt(body.private_key)
    if body.passphrase is not None:
        cred.encrypted_passphrase = encrypt(body.passphrase)

    await db.commit()
    await db.refresh(cred)
    return _to_response(cred)


@router.delete("/{credential_id}", status_code=204)
async def delete_credential(credential_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    await db.delete(cred)
    await db.commit()
