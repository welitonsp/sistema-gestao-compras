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

## 4. Implemented Data Model
The table `canonizacoes_produtos` stores logical mappings with tenant scope:

| Field | Type | Description |
| :--- | :--- | :--- |
| `department_id` | UUID (PK) | Tenant identifier. |
| `ean_original` | String (PK) | The EAN as received in the invoice (FK to `produtos.ean`). |
| `ean_canonico` | String | The target EAN representing the unified product (FK to `produtos.ean`). |
| `status` | String | `active`, `inactive`, or `reverted`. |
| `confirmado_por` | String | Username of the operator who performed the action. |
| `confirmado_em` | DateTime | Timestamp of confirmation. |
| `confidence_score`| Decimal | Score from the matching engine at the time of creation. |
| `reason` | Text | Justification for the grouping. |
| `revertido_por` | String | Username of the operator who reverted the mapping. |
| `revertido_em` | DateTime | Timestamp of logical reversion. |
| `revert_reason` | Text | Optional reason for logical reversion. |
| `created_at` | DateTime | record creation timestamp. |
| `updated_at` | DateTime | record update timestamp. |

## 5. Business Rules
- **Non-Identity:** `ean_original` cannot be equal to `ean_canonico`.
- **Tenant Boundary:** Mappings cannot cross `department_id`.
- **Human Authority:** All canonizations require explicit human confirmation via the UI.
- **No Auto-IA:** AI suggestions (H9A) are for support only and cannot trigger writes automatically.
- **Reversibility:** Every canonization must be reversible (rollback) without side effects on fiscal history.

## 6. Implemented API Surface
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

### `POST /api/v1/produtos/canonization/revert`
Soft-reverts an active mapping by setting `status = "reverted"` and filling
`revertido_por`, `revertido_em`, and `revert_reason`.

The endpoint must not mutate fiscal records, products, price history, original
descriptions, or fiscal EANs.

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
- Every reversion must be logged with the operation type `PRODUCT_CANONIZATION_REVERTED`.
- Rollback is a logical reversion: set the mapping `status` to `reverted`.
- Do not delete mappings physically as part of ordinary reversion.
- Dashboards and catalog views must consider only `status = 'active'` mappings for canonical aggregation.

## 9. Delivery Status
Completed phases:

1. **H9A-H9C:** Candidate preview, UI review, and simulator foundation.
2. **H9E-1 to H9E-5:** Persistent mapping table, confirmation endpoint, dashboard integration, catalog badges, reversion endpoint, and catalog reversion UI.
3. **H9E-6:** Administrative read-only mappings view baseline.
4. **H9G:** Dashboard Comparativo MVP with explicit behavior for the `Tudo` period.
5. **H9F/H10B:** CSV and AuditLog sanitization hardening.
6. **H10A-H10E:** Tenant-aware `ClassificacaoCache`, AI cache scope propagation, tenant-scoped category context for import prompts, and tenant-scoped catalog maintenance suggestions.

Future work should focus on operational polish, richer administrative filters,
exports/history where needed, and final manual QA of analytics rather than
rebuilding the mapping/reversion foundation.

## 10. Anti-Patterns (What NOT to do)
- **Do NOT** change `ItemNotaFiscal.ean`. It is an immutable fiscal record.
- **Do NOT** delete records from the `produtos` table.
- **Do NOT** alter the `descricao_original` field.
- **Do NOT** perform global canonizations without `department_id`.
- **Do NOT** allow the system to automatically merge products based on high fuzzy scores without human review.
