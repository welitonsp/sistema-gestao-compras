import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from backend.models.compras import Fornecedor, NotaFiscal, Department, User, UserRole
from backend.services.repository import ProcurementRepository
from backend.schemas.internal import NotaFiscalDTO, FornecedorDTO, ItemNotaDTO

from backend.core.database import SessionLocal

@pytest.mark.asyncio
async def test_duplicate_cnpj_different_departments():
    async with SessionLocal() as db_session:
        repo = ProcurementRepository(db_session)
        
        dept1 = Department(name="Dept 1")
        dept2 = Department(name="Dept 2")
        db_session.add_all([dept1, dept2])
        await db_session.flush()
        
        cnpj = "12345678000199"
        
        # Criar fornecedor no Dept 1
        forn1_dto = FornecedorDTO(cnpj=cnpj, razao_social="Forn 1")
        forn1 = await repo._obter_ou_criar_fornecedor(forn1_dto, department_id=dept1.id)
        
        # Criar fornecedor no Dept 2 (mesmo CNPJ)
        forn2_dto = FornecedorDTO(cnpj=cnpj, razao_social="Forn 2")
        forn2 = await repo._obter_ou_criar_fornecedor(forn2_dto, department_id=dept2.id)
        
        assert forn1.id != forn2.id
        assert forn1.department_id == dept1.id
        assert forn2.department_id == dept2.id
        
        # Verificar no banco
        res = await db_session.execute(select(Fornecedor).where(Fornecedor.cnpj == cnpj))
        fornecedores = res.scalars().all()
        assert len(fornecedores) == 2

@pytest.mark.asyncio
async def test_duplicate_access_key_different_departments():
    async with SessionLocal() as db_session:
        repo = ProcurementRepository(db_session)
        
        dept1 = Department(name="Dept A")
        dept2 = Department(name="Dept B")
        db_session.add_all([dept1, dept2])
        await db_session.flush()
        
        chave = "1" * 44
        dto = NotaFiscalDTO(
            chave_acesso=chave,
            numero_nota="101",
            data_emissao=date.today(),
            valor_total=Decimal("100.00"),
            fornecedor=FornecedorDTO(cnpj="111", razao_social="Forn"),
            itens=[ItemNotaDTO(codigo_produto="P1", descricao="Prod", quantidade=1, valor_unitario=100, valor_total=100)]
        )
        
        # Salvar no Dept 1
        await repo.salvar_nota_completa(chave, dto, department_id=dept1.id)
        
        # Tentar salvar no Dept 2 (Deve permitir agora)
        await repo.salvar_nota_completa(chave, dto, department_id=dept2.id)
        
        # Verificar isolamento no nota_existe
        assert await repo.nota_existe(chave, department_id=dept1.id) is True
        assert await repo.nota_existe(chave, department_id=dept2.id) is True
        
        # Verificar total de notas com essa chave
        res = await db_session.execute(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        assert len(res.scalars().all()) == 2

@pytest.mark.asyncio
async def test_duplicate_user_credentials_different_departments():
    async with SessionLocal() as db_session:
        dept1 = Department(name="SaaS A")
        dept2 = Department(name="SaaS B")
        db_session.add_all([dept1, dept2])
        await db_session.flush()
        
        user1 = User(
            username="admin", 
            email="admin@test.com", 
            hashed_password="...", 
            department_id=dept1.id,
            role=UserRole.ADMIN
        )
        user2 = User(
            username="admin", 
            email="admin@test.com", 
            hashed_password="...", 
            department_id=dept2.id,
            role=UserRole.ADMIN
        )
        
        db_session.add_all([user1, user2])
        await db_session.commit() # Se falhar aqui, a constraint não está funcionando como multi-tenant
        
        res = await db_session.execute(select(User).where(User.username == "admin"))
        assert len(res.scalars().all()) == 2
