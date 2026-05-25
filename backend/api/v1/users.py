"""Routes for user and department management."""

from __future__ import annotations

from typing import Any, List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from backend.api.dependencies import DbSession, CurrentUser, RoleChecker
from backend.models.compras import User, UserRole, Department
from backend.core.security import get_password_hash
from backend.schemas.users import UserResponse, UserCreate, UserUpdate, DepartmentResponse

router = APIRouter(prefix="/users", tags=["Gestão de Usuários"])

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obter perfil do usuário atual"
)
async def obter_me(user: CurrentUser):
    """Retorna os dados do usuário autenticado via cookie."""
    return user

@router.get(
    "",
    response_model=List[UserResponse],
    summary="Listar usuários (Apenas Admin)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def listar_usuarios(db: DbSession):
    """Retorna a lista de todos os usuários do sistema."""
    stmt = select(User).order_by(User.username)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo usuário",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def criar_usuario(payload: UserCreate, db: DbSession):
    """Cria um novo usuário com senha criptografada."""
    # Verifica se já existe
    stmt = select(User).where(User.username == payload.username)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nome de usuário já existe.")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        department_id=payload.department_id,
        is_active=payload.is_active
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Atualizar usuário",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def atualizar_usuario(user_id: str, payload: UserUpdate, db: DbSession):
    """Atualiza dados de perfil, role ou estado ativo do usuário."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user

@router.get(
    "/departments",
    response_model=List[DepartmentResponse],
    summary="Listar departamentos"
)
async def listar_departamentos(db: DbSession, user: CurrentUser):
    """Retorna os departamentos ativos no sistema."""
    stmt = select(Department).where(Department.is_active == True)
    result = await db.execute(stmt)
    return result.scalars().all()
