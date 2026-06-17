from __future__ import annotations

import json
import re
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from .config import Settings


DbRow = dict[str, Any]


def validate_table_name(table_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    return table_name


@contextmanager
def postgres_connection(settings: Settings) -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        yield connection
    finally:
        connection.close()


def init_database(settings: Settings) -> None:
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS product_catalog (
                    id SERIAL PRIMARY KEY,
                    sku TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    department TEXT NOT NULL,
                    unit_measure TEXT NOT NULL,
                    supplier_name TEXT NOT NULL,
                    cost_price DOUBLE PRECISION NOT NULL,
                    selling_price DOUBLE PRECISION NOT NULL,
                    gross_margin_pct DOUBLE PRECISION NOT NULL,
                    current_stock_qty DOUBLE PRECISION NOT NULL,
                    reorder_point_qty DOUBLE PRECISION NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active', 'inactive')),
                    last_inventory_at DATE NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    id SERIAL PRIMARY KEY,
                    sale_date DATE NOT NULL,
                    sku TEXT NOT NULL,
                    product_description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quantity_sold DOUBLE PRECISION NOT NULL,
                    unit_price DOUBLE PRECISION NOT NULL,
                    gross_revenue DOUBLE PRECISION NOT NULL,
                    discount_value DOUBLE PRECISION NOT NULL,
                    net_revenue DOUBLE PRECISION NOT NULL,
                    cash_generation DOUBLE PRECISION NOT NULL,
                    payment_method TEXT NOT NULL,
                    sales_channel TEXT NOT NULL,
                    shift TEXT NOT NULL,
                    FOREIGN KEY (sku) REFERENCES product_catalog(sku)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    id SERIAL PRIMARY KEY,
                    id_colaborador TEXT NOT NULL UNIQUE,
                    employee_name TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    role_name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('a', 'i')),
                    primary_shift TEXT NOT NULL,
                    cross_trained_sectors TEXT,
                    weekly_hours INTEGER NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS absenteeism_events (
                    id SERIAL PRIMARY KEY,
                    event_date DATE NOT NULL,
                    id_colaborador TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    scheduled_shift TEXT NOT NULL,
                    absence_type TEXT NOT NULL,
                    absence_hours DOUBLE PRECISION NOT NULL,
                    coverage_priority TEXT NOT NULL,
                    replacement_required BOOLEAN NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (id_colaborador) REFERENCES employees(id_colaborador)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    store_id TEXT,
                    title TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    conversation_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    summarized_until_message_id INTEGER NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_memories (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    store_id TEXT,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evolution_instance_state (
                    instance_id TEXT PRIMARY KEY,
                    instance_name TEXT,
                    instance_token TEXT,
                    last_event TEXT,
                    connection_status TEXT,
                    qr_code_base64 TEXT,
                    phone_jid TEXT,
                    push_name TEXT,
                    metadata_json TEXT,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evolution_processed_messages (
                    instance_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (instance_id, message_id)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_product_catalog_sku ON product_catalog(sku)"
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_sku ON sales(sku)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_employees_sector_status ON employees(sector, status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_absenteeism_event_date ON absenteeism_events(event_date)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id ON conversation_messages(conversation_id, id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_memories_user_store ON user_memories(user_id, store_id, priority)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_evolution_instance_state_name ON evolution_instance_state(instance_name)"
            )
        connection.commit()


def seed_database(settings: Settings) -> dict[str, int]:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE
                    absenteeism_events,
                    sales,
                    employees,
                    product_catalog
                RESTART IDENTITY CASCADE
                """
            )

            products = [
                ("AP001", "Pastilha de freio dianteira ceramic", "freios", "autopecas", "jogo", "FreioMax Distribuidora", 78.90, 129.90, 64.64, 34.0, 12.0, "active", "2026-06-15"),
                ("AP002", "Disco de freio ventilado aro 14", "freios", "autopecas", "un", "MetalBrake", 92.50, 156.90, 69.62, 18.0, 8.0, "active", "2026-06-15"),
                ("AP003", "Oleo sintetico 5W30 1L", "lubrificantes", "autopecas", "lt", "LubriOne", 21.40, 36.90, 72.43, 72.0, 24.0, "active", "2026-06-15"),
                ("AP004", "Filtro de oleo universal", "filtros", "autopecas", "un", "FiltroTech", 14.80, 28.90, 95.27, 46.0, 15.0, "active", "2026-06-15"),
                ("AP005", "Bateria automotiva 60Ah", "eletrica", "autopecas", "un", "PowerVolt", 248.00, 379.90, 53.19, 9.0, 4.0, "active", "2026-06-15"),
                ("AP006", "Amortecedor dianteiro pressurizado", "suspensao", "autopecas", "un", "RidePro", 132.00, 214.90, 62.8, 16.0, 6.0, "active", "2026-06-15"),
                ("AP007", "Kit correia dentada completo", "motor", "autopecas", "kit", "MotorSync", 168.50, 279.90, 66.11, 11.0, 5.0, "active", "2026-06-15"),
                ("AP008", "Jogo de velas de ignicao iridium", "ignicao", "autopecas", "jogo", "SparkLine", 88.20, 149.90, 69.95, 21.0, 8.0, "active", "2026-06-15"),
                ("AP009", "Filtro de ar do motor", "filtros", "autopecas", "un", "FiltroTech", 16.70, 31.90, 91.02, 39.0, 14.0, "active", "2026-06-15"),
                ("AP010", "Palheta limpador 24 polegadas", "acessorios", "autopecas", "un", "VisionParts", 11.90, 24.90, 109.24, 54.0, 20.0, "active", "2026-06-15"),
                ("AP011", "Lampada halogena H7 12V", "eletrica", "autopecas", "par", "LumiCar", 18.30, 34.90, 90.71, 33.0, 12.0, "active", "2026-06-15"),
                ("AP012", "Aditivo para radiador 1L", "arrefecimento", "autopecas", "lt", "CoolFlow", 12.60, 25.90, 105.56, 28.0, 10.0, "active", "2026-06-15"),
                ("AP013", "Pivo de suspensao inferior", "suspensao", "autopecas", "un", "RidePro", 34.20, 68.90, 101.46, 17.0, 7.0, "active", "2026-06-15"),
                ("AP014", "Terminal de direcao", "direcao", "autopecas", "un", "SteerMax", 29.80, 59.90, 101.01, 13.0, 6.0, "active", "2026-06-15"),
                ("AP015", "Kit de embreagem completo", "transmissao", "autopecas", "kit", "TorqueDrive", 242.00, 398.90, 64.83, 8.0, 4.0, "active", "2026-06-15"),
                ("AP016", "Fluido de freio DOT4 500ml", "freios", "autopecas", "un", "FreioMax Distribuidora", 9.40, 19.90, 111.7, 31.0, 10.0, "active", "2026-06-15"),
                ("AP017", "Sensor ABS dianteiro", "eletrica", "autopecas", "un", "ElectroParts", 74.60, 132.90, 78.15, 10.0, 4.0, "active", "2026-06-15"),
                ("AP018", "Rolamento de roda traseira", "suspensao", "autopecas", "un", "RidePro", 58.20, 109.90, 88.83, 12.0, 5.0, "active", "2026-06-15"),
            ]
            cursor.executemany(
                """
                INSERT INTO product_catalog
                (
                    sku, description, category, department, unit_measure, supplier_name,
                    cost_price, selling_price, gross_margin_pct, current_stock_qty,
                    reorder_point_qty, status, last_inventory_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                products,
            )

            employees = [
                ("C1001", "Ana Paula Souza", "caixa", "Operadora de caixa", "a", "manha", "vendas_balcao,televendas", 44),
                ("C1002", "Bruno Henrique Lima", "vendas_balcao", "Vendedor tecnico senior", "a", "manha", "estoque,televendas", 44),
                ("C1003", "Carla Mendes Rocha", "vendas_balcao", "Vendedora tecnica", "a", "tarde", "caixa,televendas", 44),
                ("C1004", "Diego Martins", "recebimento", "Conferente de mercadorias", "a", "manha", "estoque,expedicao", 44),
                ("C1005", "Elaine Cristina", "caixa", "Fiscal de caixa", "a", "tarde", "vendas_balcao,televendas", 44),
                ("C1006", "Fabio Nogueira", "estoque", "Auxiliar de estoque", "a", "noite", "recebimento,expedicao", 44),
                ("C1007", "Gabriela Pires", "estoque", "Lider de estoque", "a", "manha", "recebimento,expedicao,vendas_balcao", 44),
                ("C1008", "Helio Barbosa", "expedicao", "Auxiliar de expedicao", "i", "manha", "estoque,recebimento", 44),
                ("C1009", "Isabela Freitas", "televendas", "Atendente de televendas", "a", "tarde", "vendas_balcao,caixa", 36),
                ("C1010", "Joao Victor Alves", "recebimento", "Auxiliar de carga", "a", "manha", "estoque,expedicao", 44),
                ("C1011", "Karen Ribeiro", "estoque", "Separadora de pedidos", "a", "noite", "expedicao,vendas_balcao", 36),
                ("C1012", "Lucas Ferreira", "caixa", "Assistente de loja", "a", "tarde", "televendas,vendas_balcao", 36),
                ("C1013", "Mariana Costa", "televendas", "Consultora de pecas", "a", "manha", "vendas_balcao,caixa", 44),
                ("C1014", "Rafael Gomes", "expedicao", "Motorista interno", "a", "tarde", "estoque,recebimento", 44),
            ]
            cursor.executemany(
                """
                INSERT INTO employees
                (
                    id_colaborador, employee_name, sector, role_name, status, primary_shift,
                    cross_trained_sectors, weekly_hours
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                employees,
            )

            sales = [
                ("2026-06-09", "AP003", "Oleo sintetico 5W30 1L", "lubrificantes", 14.0, 36.90, 516.60, 22.80, 493.80, 493.80, "pix", "loja_fisica", "manha"),
                ("2026-06-09", "AP001", "Pastilha de freio dianteira ceramic", "freios", 5.0, 129.90, 649.50, 35.00, 614.50, 596.07, "credito", "vendas_balcao", "tarde"),
                ("2026-06-09", "AP010", "Palheta limpador 24 polegadas", "acessorios", 11.0, 24.90, 273.90, 8.90, 265.00, 265.00, "debito", "loja_fisica", "noite"),
                ("2026-06-10", "AP004", "Filtro de oleo universal", "filtros", 16.0, 28.90, 462.40, 18.00, 444.40, 444.40, "pix", "televendas", "manha"),
                ("2026-06-10", "AP008", "Jogo de velas de ignicao iridium", "ignicao", 6.0, 149.90, 899.40, 30.00, 869.40, 843.32, "credito", "vendas_balcao", "tarde"),
                ("2026-06-10", "AP012", "Aditivo para radiador 1L", "arrefecimento", 9.0, 25.90, 233.10, 6.00, 227.10, 227.10, "dinheiro", "loja_fisica", "noite"),
                ("2026-06-11", "AP005", "Bateria automotiva 60Ah", "eletrica", 3.0, 379.90, 1139.70, 45.00, 1094.70, 1061.86, "credito", "vendas_balcao", "manha"),
                ("2026-06-11", "AP009", "Filtro de ar do motor", "filtros", 10.0, 31.90, 319.00, 10.00, 309.00, 309.00, "pix", "televendas", "tarde"),
                ("2026-06-11", "AP016", "Fluido de freio DOT4 500ml", "freios", 13.0, 19.90, 258.70, 5.20, 253.50, 253.50, "debito", "loja_fisica", "noite"),
                ("2026-06-12", "AP007", "Kit correia dentada completo", "motor", 4.0, 279.90, 1119.60, 40.00, 1079.60, 1047.21, "credito", "vendas_balcao", "manha"),
                ("2026-06-12", "AP011", "Lampada halogena H7 12V", "eletrica", 12.0, 34.90, 418.80, 12.00, 406.80, 406.80, "pix", "loja_fisica", "tarde"),
                ("2026-06-12", "AP013", "Pivo de suspensao inferior", "suspensao", 7.0, 68.90, 482.30, 14.00, 468.30, 454.25, "debito", "televendas", "noite"),
                ("2026-06-13", "AP002", "Disco de freio ventilado aro 14", "freios", 4.0, 156.90, 627.60, 25.00, 602.60, 584.52, "credito", "vendas_balcao", "manha"),
                ("2026-06-13", "AP006", "Amortecedor dianteiro pressurizado", "suspensao", 5.0, 214.90, 1074.50, 32.00, 1042.50, 1011.22, "pix", "vendas_balcao", "tarde"),
                ("2026-06-13", "AP003", "Oleo sintetico 5W30 1L", "lubrificantes", 18.0, 36.90, 664.20, 21.60, 642.60, 642.60, "dinheiro", "loja_fisica", "noite"),
                ("2026-06-14", "AP015", "Kit de embreagem completo", "transmissao", 2.0, 398.90, 797.80, 18.00, 779.80, 756.41, "credito", "vendas_balcao", "manha"),
                ("2026-06-14", "AP014", "Terminal de direcao", "direcao", 8.0, 59.90, 479.20, 16.00, 463.20, 449.30, "pix", "televendas", "tarde"),
                ("2026-06-14", "AP004", "Filtro de oleo universal", "filtros", 19.0, 28.90, 549.10, 13.30, 535.80, 535.80, "debito", "marketplace", "noite"),
                ("2026-06-15", "AP005", "Bateria automotiva 60Ah", "eletrica", 4.0, 379.90, 1519.60, 60.00, 1459.60, 1415.81, "credito", "vendas_balcao", "manha"),
                ("2026-06-15", "AP001", "Pastilha de freio dianteira ceramic", "freios", 7.0, 129.90, 909.30, 28.00, 881.30, 854.86, "pix", "loja_fisica", "manha"),
                ("2026-06-15", "AP003", "Oleo sintetico 5W30 1L", "lubrificantes", 22.0, 36.90, 811.80, 24.00, 787.80, 787.80, "dinheiro", "loja_fisica", "tarde"),
                ("2026-06-15", "AP007", "Kit correia dentada completo", "motor", 3.0, 279.90, 839.70, 21.00, 818.70, 794.14, "credito", "televendas", "tarde"),
                ("2026-06-15", "AP010", "Palheta limpador 24 polegadas", "acessorios", 15.0, 24.90, 373.50, 10.50, 363.00, 363.00, "debito", "marketplace", "noite"),
                ("2026-06-15", "AP017", "Sensor ABS dianteiro", "eletrica", 4.0, 132.90, 531.60, 16.00, 515.60, 500.13, "pix", "vendas_balcao", "noite"),
            ]
            cursor.executemany(
                """
                INSERT INTO sales
                (
                    sale_date, sku, product_description, category, quantity_sold, unit_price,
                    gross_revenue, discount_value, net_revenue, cash_generation, payment_method,
                    sales_channel, shift
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                sales,
            )

            absenteeism_events = [
                ("2026-06-10", "C1004", "recebimento", "manha", "consulta_medica", 4.0, "alta", True, "Recebimento de baterias e discos de freio precisou de apoio do estoque."),
                ("2026-06-11", "C1009", "televendas", "tarde", "falta_nao_justificada", 6.0, "media", True, "Fila de orcamentos por WhatsApp aumentou no fim da tarde."),
                ("2026-06-12", "C1006", "estoque", "noite", "atestado_medico", 8.0, "alta", True, "Separacao de kits de embreagem e correias ficou abaixo do planejado."),
                ("2026-06-13", "C1014", "expedicao", "tarde", "falta_justificada", 8.0, "media", True, "Despacho de pedidos do marketplace exigiu remanejamento do estoque."),
                ("2026-06-14", "C1001", "caixa", "manha", "consulta_medica", 4.0, "baixa", False, "Cobertura parcial feita pela fiscal de caixa."),
                ("2026-06-15", "C1002", "vendas_balcao", "manha", "atestado_medico", 8.0, "alta", True, "Atendimento tecnico no balcao perdeu o vendedor de maior ticket medio."),
                ("2026-06-15", "C1010", "recebimento", "manha", "falta_nao_justificada", 8.0, "alta", True, "Conferencia de mercadoria e entrada de notas ficaram concentradas em um unico colaborador."),
                ("2026-06-15", "C1013", "televendas", "manha", "licenca_curta", 4.0, "media", True, "Equipe de orcamento remoto ficou reduzida em horario de pico."),
            ]
            cursor.executemany(
                """
                INSERT INTO absenteeism_events
                (
                    event_date, id_colaborador, sector, scheduled_shift, absence_type,
                    absence_hours, coverage_priority, replacement_required, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                absenteeism_events,
            )
        connection.commit()

    return {
        "product_catalog": len(products),
        "sales": len(sales),
        "employees": len(employees),
        "absenteeism_events": len(absenteeism_events),
    }


def fetch_rows_for_indexing(settings: Settings) -> dict[str, list[DbRow]]:
    init_database(settings)
    rows_by_table: dict[str, list[DbRow]] = {}
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            for table_name in settings.source_table_list:
                safe_table_name = validate_table_name(table_name)
                query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(safe_table_name))
                cursor.execute(query)
                rows_by_table[table_name] = cursor.fetchall()
    return rows_by_table


def describe_schema(settings: Settings) -> str:
    init_database(settings)
    descriptions: list[str] = []
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            for table_name in settings.source_table_list:
                safe_table_name = validate_table_name(table_name)
                cursor.execute(
                    """
                    SELECT column_name, data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (safe_table_name,),
                )
                columns = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = %s
                      AND tc.constraint_type = 'PRIMARY KEY'
                    """,
                    (safe_table_name,),
                )
                primary_keys = {row["column_name"] for row in cursor.fetchall()}

                descriptions.append(f"Table {safe_table_name}:")
                for column in columns:
                    type_name = column["data_type"]
                    if type_name == "USER-DEFINED":
                        type_name = column["udt_name"]
                    descriptions.append(
                        f"- {column['column_name']} ({type_name})"
                        + (" PRIMARY KEY" if column["column_name"] in primary_keys else "")
                    )
    return "\n".join(descriptions)


def run_read_only_query(settings: Settings, query: str) -> list[DbRow]:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchmany(settings.sql_max_rows)
    return rows


def upsert_conversation(
    settings: Settings,
    conversation_id: str,
    user_id: str,
    store_id: str | None = None,
    title: str | None = None,
) -> None:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversations (conversation_id, user_id, store_id, title)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    store_id = COALESCE(EXCLUDED.store_id, conversations.store_id),
                    title = COALESCE(conversations.title, EXCLUDED.title),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (conversation_id, user_id, store_id, title),
            )
        connection.commit()


def append_conversation_message(
    settings: Settings,
    conversation_id: str,
    role: str,
    content: str,
) -> int:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (conversation_id, role, content),
            )
            message_id = int(cursor.fetchone()["id"])
            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
        connection.commit()
    return message_id


def fetch_conversation_messages(
    settings: Settings,
    conversation_id: str,
    limit: int | None = None,
    after_message_id: int | None = None,
) -> list[DbRow]:
    init_database(settings)
    query = """
        SELECT id, conversation_id, role, content, created_at
        FROM conversation_messages
        WHERE conversation_id = %s
    """
    parameters: list[object] = [conversation_id]

    if after_message_id is not None:
        query += " AND id > %s"
        parameters.append(after_message_id)

    query += " ORDER BY id ASC"

    if limit is not None:
        query += " LIMIT %s"
        parameters.append(limit)

    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            rows = cursor.fetchall()
    return rows


def fetch_recent_conversation_messages(
    settings: Settings,
    conversation_id: str,
    limit: int,
) -> list[DbRow]:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, conversation_id, role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (conversation_id, limit),
            )
            rows = cursor.fetchall()
    return list(reversed(rows))


def count_conversation_messages(settings: Settings, conversation_id: str) -> int:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM conversation_messages WHERE conversation_id = %s",
                (conversation_id,),
            )
            row = cursor.fetchone()
    return int(row["total"])


def fetch_conversation_summary(settings: Settings, conversation_id: str) -> DbRow | None:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT conversation_id, summary, summarized_until_message_id, updated_at
                FROM conversation_summaries
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()
    return row


def upsert_conversation_summary(
    settings: Settings,
    conversation_id: str,
    summary: str,
    summarized_until_message_id: int,
) -> None:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversation_summaries
                (conversation_id, summary, summarized_until_message_id, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (conversation_id) DO UPDATE SET
                    summary = EXCLUDED.summary,
                    summarized_until_message_id = EXCLUDED.summarized_until_message_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (conversation_id, summary, summarized_until_message_id),
            )
        connection.commit()


def insert_user_memory(
    settings: Settings,
    user_id: str,
    content: str,
    memory_type: str = "note",
    store_id: str | None = None,
    priority: int = 1,
) -> int:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_memories
                (user_id, store_id, memory_type, content, priority)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, store_id, memory_type, content, priority),
            )
            memory_id = int(cursor.fetchone()["id"])
        connection.commit()
    return memory_id


def fetch_user_memories(
    settings: Settings,
    user_id: str,
    limit: int,
    store_id: str | None = None,
) -> list[DbRow]:
    init_database(settings)
    query = """
        SELECT id, user_id, store_id, memory_type, content, priority, created_at, updated_at
        FROM user_memories
        WHERE user_id = %s
    """
    parameters: list[object] = [user_id]

    if store_id:
        query += " AND (store_id = %s OR store_id IS NULL)"
        parameters.append(store_id)

    query += " ORDER BY priority DESC, updated_at DESC, id DESC LIMIT %s"
    parameters.append(limit)

    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            rows = cursor.fetchall()
    return rows


def list_conversations(
    settings: Settings,
    user_id: str | None = None,
    limit: int = 20,
) -> list[DbRow]:
    init_database(settings)
    query = """
        SELECT conversation_id, user_id, store_id, title, created_at, updated_at
        FROM conversations
    """
    parameters: list[object] = []

    if user_id:
        query += " WHERE user_id = %s"
        parameters.append(user_id)

    query += " ORDER BY updated_at DESC LIMIT %s"
    parameters.append(limit)

    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            rows = cursor.fetchall()
    return rows


def fetch_conversation(settings: Settings, conversation_id: str) -> DbRow | None:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT conversation_id, user_id, store_id, title, created_at, updated_at
                FROM conversations
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()
    return row


def upsert_evolution_instance_state(
    settings: Settings,
    instance_id: str,
    instance_name: str | None = None,
    instance_token: str | None = None,
    last_event: str | None = None,
    connection_status: str | None = None,
    qr_code_base64: str | None = None,
    phone_jid: str | None = None,
    push_name: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    init_database(settings)
    metadata_json = json.dumps(metadata, ensure_ascii=True) if metadata is not None else None
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO evolution_instance_state
                (
                    instance_id,
                    instance_name,
                    instance_token,
                    last_event,
                    connection_status,
                    qr_code_base64,
                    phone_jid,
                    push_name,
                    metadata_json,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (instance_id) DO UPDATE SET
                    instance_name = COALESCE(EXCLUDED.instance_name, evolution_instance_state.instance_name),
                    instance_token = COALESCE(EXCLUDED.instance_token, evolution_instance_state.instance_token),
                    last_event = COALESCE(EXCLUDED.last_event, evolution_instance_state.last_event),
                    connection_status = COALESCE(EXCLUDED.connection_status, evolution_instance_state.connection_status),
                    qr_code_base64 = COALESCE(EXCLUDED.qr_code_base64, evolution_instance_state.qr_code_base64),
                    phone_jid = COALESCE(EXCLUDED.phone_jid, evolution_instance_state.phone_jid),
                    push_name = COALESCE(EXCLUDED.push_name, evolution_instance_state.push_name),
                    metadata_json = COALESCE(EXCLUDED.metadata_json, evolution_instance_state.metadata_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    instance_id,
                    instance_name,
                    instance_token,
                    last_event,
                    connection_status,
                    qr_code_base64,
                    phone_jid,
                    push_name,
                    metadata_json,
                ),
            )
        connection.commit()


def fetch_evolution_instance_state(settings: Settings, instance_id: str) -> DbRow | None:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    instance_id,
                    instance_name,
                    instance_token,
                    last_event,
                    connection_status,
                    qr_code_base64,
                    phone_jid,
                    push_name,
                    metadata_json,
                    updated_at
                FROM evolution_instance_state
                WHERE instance_id = %s
                """,
                (instance_id,),
            )
            row = cursor.fetchone()
    return row


def fetch_evolution_instance_state_by_name(
    settings: Settings, instance_name: str
) -> DbRow | None:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    instance_id,
                    instance_name,
                    instance_token,
                    last_event,
                    connection_status,
                    qr_code_base64,
                    phone_jid,
                    push_name,
                    metadata_json,
                    updated_at
                FROM evolution_instance_state
                WHERE instance_name = %s
                """,
                (instance_name,),
            )
            row = cursor.fetchone()
    return row


def list_evolution_instance_states(settings: Settings) -> list[DbRow]:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    instance_id,
                    instance_name,
                    instance_token,
                    last_event,
                    connection_status,
                    qr_code_base64,
                    phone_jid,
                    push_name,
                    metadata_json,
                    updated_at
                FROM evolution_instance_state
                ORDER BY updated_at DESC
                """
            )
            rows = cursor.fetchall()
    return rows


def register_processed_evolution_message(
    settings: Settings,
    instance_id: str,
    message_id: str,
) -> bool:
    init_database(settings)
    with postgres_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO evolution_processed_messages (instance_id, message_id)
                VALUES (%s, %s)
                ON CONFLICT (instance_id, message_id) DO NOTHING
                RETURNING message_id
                """,
                (instance_id, message_id),
            )
            row = cursor.fetchone()
        connection.commit()
    return row is not None
