# Architectural Decision Record (ADR): Persistent Product Canonization

## 1. Context
The system currently implements a three-stage read-only foundation for product management:
- **H9A (Backend Preview):** Strong normalization and conservative fuzzy matching using RapidFuzz.
- **H9B (UI Preview):** A read-only review interface for candidates.
- **H9C (Simulator):** A local/frontend-only simulation of canonization plans.
- **H9D (Audit):** An architectural audit that recommended a logical mapping layer instead of direct record mutation.

## 2. Problem Statement
- **Global PK:** The `Produto.ean` field is a primary key and global across all tenants (departments).
- **Tenant Isolation:** Products do not have a `department_id`. Direct mutation of a product's name or category would affect all departments, violating multi-tenancy isolation.
- **Fiscal Integrity:** Fiscal data extracted from invoices (descriptions and EANs) must remain intact for legal and audit purposes.
- **Duplicate EANs/Internal Codes:** Suppliers often use different EANs or internal codes for the same physical product, leading to fragmented price history and dashboards.

## 3. Decision: Logical Mapping Layer
We will adopt a **Logical Mapping Layer (Canonization Aliasing)** by `department_id`.
- **Preservation:** The `Produto` table and `ItemNotaFiscal` table remain untouched.
- **Abstraction:** A new mapping table will act as a "lens" that translates a supplier-provided EAN to a department-preferred "Canonical EAN".
- **Scope:** Canonization is scoped to each `department_id`.

## 4. Conceptual Data Model
A new table `canonizacoes_produtos` will be created with the following structure:

| Field | Type | Description |
| :--- | :--- | :--- |
| `department_id` | UUID (PK) | Tenant identifier. |
| `ean_original` | String (PK) | The EAN as received in the invoice (FK to `produtos.ean`). |
| `ean_canonico` | String | The target EAN representing the unified product (FK to `produtos.ean`). |
| `status` | String | `active` or `revoked`. |
| `confirmado_por` | String | Username of the operator who performed the action. |
| `confirmado_em` | DateTime | Timestamp of confirmation. |
| `confidence_score`| Decimal | Score from the matching engine at the time of creation. |
| `reason` | Text | Justification for the grouping. |
| `created_at` | DateTime | record creation timestamp. |
| `updated_at` | DateTime | record update timestamp. |

## 5. Business Rules
- **Non-Identity:** `ean_original` cannot be equal to `ean_canonico`.
- **Tenant Boundary:** Mappings cannot cross `department_id`.
- **Human Authority:** All canonizations require explicit human confirmation via the UI.
- **No Auto-IA:** AI suggestions (H9A) are for support only and cannot trigger writes automatically.
- **Reversibility:** Every canonization must be reversible (rollback) without side effects on fiscal history.

## 6. Future API Specification (H9E-2)
### `POST /api/v1/produtos/canonization/confirm`
**Request Payload:**
```json
{
  "ean_canonico": "7891234567890",
  "eans_originais": ["7890001112223", "7899998887776"],
  "reason": "Unificação de embalagens de Arroz 5kg de diferentes fornecedores."
}
```
**Validations:**
1. Verify all EANs exist in the `produtos` table.
2. Verify `ean_canonico` is not present in `eans_originais`.
3. Verify the user has `ADMIN` or `MANAGER` role for the `department_id`.
4. Create `AuditLog` entries for each mapping.

## 7. Impact on Dashboards & Reports
Reports must decide whether to use the **Fiscal View** or the **Canonical View**.
- **Canonical Query Logic:**
  ```sql
  SELECT 
    COALESCE(map.ean_canonico, item.ean) as ean_exibicao,
    SUM(item.valor_total) as total
  FROM itens_notas_fiscais item
  LEFT JOIN canonizacoes_produtos map 
    ON item.ean = map.ean_original 
    AND map.department_id = :dept_id
    AND map.status = 'active'
  GROUP BY 1;
  ```

## 8. Auditability & Rollback
- Every write action must be logged in the `audit_logs` table with the operation type `PRODUCT_CANONIZED`.
- Rollback will be implemented by setting the mapping `status` to `revoked` or deleting the row, immediately restoring the original dashboard view.

## 9. Future Roadmap Phases
1. **H9E-1 (Infrastructure):** Database migration and SQLAlchemy model creation.
2. **H9E-2 (Service):** Backend service logic and confirmation endpoint.
3. **H9E-3 (Dashboards):** Updating core dashboard queries to respect the mapping layer.
4. **H9E-4 (UI Integration):** Transforming the simulator (H9C) into a functional confirmation tool.
5. **H9E-5 (Admin):** UI for managing/revoking existing canonizations.

## 10. Anti-Patterns (What NOT to do)
- **Do NOT** change `ItemNotaFiscal.ean`. It is an immutable fiscal record.
- **Do NOT** delete records from the `produtos` table.
- **Do NOT** alter the `descricao_original` field.
- **Do NOT** perform global canonizations without `department_id`.
- **Do NOT** allow the system to automatically merge products based on high fuzzy scores without human review.
