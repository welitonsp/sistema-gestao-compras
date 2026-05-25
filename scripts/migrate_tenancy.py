import asyncio
from backend.core.database import SessionLocal
from backend.models.compras import User, Department
from sqlalchemy import select, update

async def fix_tenancy():
    async with SessionLocal() as db:
        # 1. Garante Departamento
        stmt_dept = select(Department).where(Department.name == "Institucional")
        res_dept = await db.execute(stmt_dept)
        dept = res_dept.scalar_one_or_none()
        
        if not dept:
            dept = Department(name="Institucional", description="Departamento Principal")
            db.add(dept)
            await db.flush()
        
        # 2. Vincula usuários sem departamento
        await db.execute(
            update(User)
            .where(User.department_id == None)
            .values(department_id=dept.id)
        )
        
        # 3. Vincula notas sem departamento
        from backend.models.compras import NotaFiscal
        await db.execute(
            update(NotaFiscal)
            .where(NotaFiscal.department_id == None)
            .values(department_id=dept.id)
        )

        await db.commit()
        print(f"✅ Tenancy migrada para o departamento '{dept.name}'.")

if __name__ == "__main__":
    asyncio.run(fix_tenancy())
