from __future__ import annotations

import sqlite3

from langchain_core.documents import Document


def translate_employee_status(status: str) -> str:
    mapping = {
        "a": "ativo",
        "i": "inativo",
    }
    return mapping.get(status.lower(), status)


def render_row(table_name: str, row: sqlite3.Row) -> str:
    if table_name == "product_catalog":
        return (
            "Tipo de documento: cadastro de produto\n"
            f"SKU: {row['sku']}\n"
            f"Descricao: {row['description']}\n"
            f"Categoria: {row['category']}\n"
            f"Departamento: {row['department']}\n"
            f"Unidade de medida: {row['unit_measure']}\n"
            f"Fornecedor: {row['supplier_name']}\n"
            f"Preco de custo: {row['cost_price']}\n"
            f"Preco de venda: {row['selling_price']}\n"
            f"Margem bruta percentual: {row['gross_margin_pct']}\n"
            f"Estoque atual: {row['current_stock_qty']}\n"
            f"Ponto de reposicao: {row['reorder_point_qty']}\n"
            f"Status: {row['status']}\n"
            f"Ultimo inventario em: {row['last_inventory_at']}"
        )

    if table_name == "sales":
        return (
            "Tipo de documento: registro de venda\n"
            f"Data da venda: {row['sale_date']}\n"
            f"SKU: {row['sku']}\n"
            f"Descricao do produto: {row['product_description']}\n"
            f"Categoria: {row['category']}\n"
            f"Quantidade vendida: {row['quantity_sold']}\n"
            f"Preco unitario: {row['unit_price']}\n"
            f"Receita bruta: {row['gross_revenue']}\n"
            f"Valor de desconto: {row['discount_value']}\n"
            f"Receita liquida: {row['net_revenue']}\n"
            f"Geracao de caixa: {row['cash_generation']}\n"
            f"Forma de pagamento: {row['payment_method']}\n"
            f"Canal de venda: {row['sales_channel']}\n"
            f"Turno: {row['shift']}"
        )

    if table_name == "employees":
        return (
            "Tipo de documento: cadastro de funcionario\n"
            f"Id do colaborador: {row['id_colaborador']}\n"
            f"Nome do colaborador: {row['employee_name']}\n"
            f"Setor: {row['sector']}\n"
            f"Cargo: {row['role_name']}\n"
            f"Status: {translate_employee_status(row['status'])} (codigo original: {row['status']})\n"
            f"Turno principal: {row['primary_shift']}\n"
            f"Setores com treinamento cruzado: {row['cross_trained_sectors'] or 'n/a'}\n"
            f"Carga horaria semanal: {row['weekly_hours']}"
        )

    if table_name == "absenteeism_events":
        return (
            "Tipo de documento: evento de absenteismo\n"
            f"Data do evento: {row['event_date']}\n"
            f"Id do colaborador: {row['id_colaborador']}\n"
            f"Setor: {row['sector']}\n"
            f"Turno previsto: {row['scheduled_shift']}\n"
            f"Tipo de ausencia: {row['absence_type']}\n"
            f"Horas de ausencia: {row['absence_hours']}\n"
            f"Prioridade de cobertura: {row['coverage_priority']}\n"
            f"Reposicao obrigatoria: {row['replacement_required']}\n"
            f"Observacoes: {row['notes'] or 'n/a'}"
        )

    lines = [f"Tipo de documento: linha de banco da tabela {table_name}"]
    for key in row.keys():
        lines.append(f"{key}: {row[key]}")
    return "\n".join(lines)


def build_documents(rows_by_table: dict[str, list[sqlite3.Row]]) -> list[Document]:
    documents: list[Document] = []
    for table_name, rows in rows_by_table.items():
        for row in rows:
            record_id = row["id"] if "id" in row.keys() else "unknown"
            source = table_name
            title = None
            if "description" in row.keys():
                title = row["description"]
            elif "employee_name" in row.keys():
                title = row["employee_name"]
            elif "product_description" in row.keys():
                title = row["product_description"]
            documents.append(
                Document(
                    page_content=render_row(table_name, row),
                    metadata={
                        "table": table_name,
                        "record_id": record_id,
                        "source": source,
                        "title": title,
                    },
                )
            )
    return documents
