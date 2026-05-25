import asyncio
import argparse
from backend.core.database import SessionLocal
from backend.models.compras import User, UserRole, Department
from backend.core.security import get_password_hash
from sqlalchemy import select

async def create_admin(username, email, password):
    async with SessionLocal() as db:
        # 1. Garante Departamento Padrão
        stmt_dept = select(Department).where(Department.name == "Institucional")
        res_dept = await db.execute(stmt_dept)
        dept = res_dept.scalar_one_or_none()
        
        if not dept:
            dept = Department(name="Institucional", description="Departamento Principal")
            db.add(dept)
            await db.flush() # Para obter o ID

        # 2. Verifica se usuário já existe
        stmt = select(User).where(User.username == username)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            print(f"❌ Erro: Usuário '{username}' já existe.")
            return

        admin = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            full_name="Administrador do Sistema",
            is_active=True,
            department_id=dept.id
        )
        db.add(admin)
        await db.commit()
        print(f"✅ Usuário SuperAdmin '{username}' criado no departamento '{dept.name}'!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap do Admin Inicial")
    parser.add_argument("--user", default="admin", help="Username")
    parser.add_argument("--email", default="admin@institucional.gov.br", help="Email")
    parser.add_argument("--password", required=True, help="Senha do Admin")
    
    args = parser.parse_args()
    asyncio.run(create_admin(args.user, args.email, args.password))
