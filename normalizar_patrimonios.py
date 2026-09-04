"""
=====================================================================
 NORMALIZADOR DE PATRIMÔNIOS - Acrescenta zeros à esquerda
=====================================================================

Objetivo:
    Padronizar todos os códigos de patrimônio para 6 dígitos,
    acrescentando zeros à esquerda.

Exemplos:
    2315   -> 002315
    145    -> 000145
    37     -> 000037
    9433   -> 009433
    703510 -> 703510 (já tem 6 dígitos, não altera)

O que é alterado:
    - TODOS os equipamentos do banco, incluindo:
      * ativos
      * em manutenção
      * baixados
      * excluídos (lixeira)

O que NÃO é alterado:
    - Manutenções e histórico (eles usam o ID interno,
      não o código de patrimônio)

Segurança:
    - Faz backup automático do banco antes de alterar:
      patrimonio_backup_YYYYmmdd_HHMMSS.db

Como usar:
    1. PARE o servidor Flask (app.py deve estar desligado).
    2. Coloque este arquivo na MESMA PASTA do app.py
       (onde está o patrimonio.db).
    3. Execute:  python normalizar_patrimonios.py
    4. Confira o resumo e ligue o Flask novamente.

=====================================================================
"""

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# -------------------------------------------------------------------
# CONFIGURAÇÕES
# -------------------------------------------------------------------

# Nome do banco de dados (mesmo usado pelo app.py)
ARQUIVO_DB = "patrimonio.db"

# Tamanho desejado para o código de patrimônio
TAMANHO = 6


# -------------------------------------------------------------------
# FUNÇÕES
# -------------------------------------------------------------------

def normalizar_codigo(codigo, tamanho=TAMANHO):
    """
    Acrescenta zeros à esquerda até atingir o tamanho.

    Regras:
    - Só altera se for composto SOMENTE por dígitos.
    - Se já tiver o tamanho (ou mais), não altera.
    - Remove espaços antes.
    """

    if codigo is None:
        return None, False

    texto = str(codigo).strip()

    if texto == "":
        return texto, False

    # Só numérico puro (permite 0 à esquerda já existente)
    if not texto.isdigit():
        return texto, False

    if len(texto) >= tamanho:
        return texto, False

    novo = texto.zfill(tamanho)

    return novo, novo != texto


def main():

    pasta = Path(__file__).resolve().parent
    caminho_db = pasta / ARQUIVO_DB

    print()
    print("=" * 70)
    print("NORMALIZADOR DE PATRIMÔNIOS")
    print("=" * 70)
    print()
    print(f"Banco de dados: {caminho_db}")

    if not caminho_db.exists():
        print()
        print(f"ERRO: banco não encontrado: {caminho_db}")
        print("Coloque este script na mesma pasta do app.py.")
        input("\nPressione ENTER para sair...")
        return

    conexao = sqlite3.connect(str(caminho_db))
    conexao.row_factory = sqlite3.Row

    # ---------------------------------------------------------------
    # 1. Carrega todos os equipamentos (ATIVOS + LIXEIRA)
    # ---------------------------------------------------------------

    linhas = conexao.execute(
        "SELECT id, barcode, nome, status, deleted_at "
        "FROM equipamento ORDER BY id"
    ).fetchall()

    print(f"Equipamentos encontrados: {len(linhas)}")
    print()

    # ---------------------------------------------------------------
    # 2. Calcula os novos códigos e detecta conflitos
    # ---------------------------------------------------------------

    # novo_codigo -> [ (id, codigo_antigo), ... ]
    mapa_novos = {}
    ja_ok = 0
    nao_numericos = []

    for linha in linhas:

        novo, altera = normalizar_codigo(
            linha["barcode"]
        )

        if not altera:

            if (
                str(linha["barcode"]).strip().isdigit()
                and len(str(linha["barcode"]).strip()) == TAMANHO
            ):
                ja_ok += 1
            else:
                nao_numericos.append(
                    (
                        linha["id"],
                        linha["barcode"],
                        linha["nome"],
                    )
                )

            continue

        mapa_novos.setdefault(novo, []).append(
            (
                linha["id"],
                linha["barcode"],
                linha["nome"],
            )
        )

    # ---------------------------------------------------------------
    # 3. Separa os que podem ser atualizados dos conflitantes
    # ---------------------------------------------------------------

    atualizacoes = []   # (id, codigo_antigo, codigo_novo)
    conflitos = []      # codigo_novo -> lista de equipamentos

    for novo, lista in mapa_novos.items():

        if len(lista) > 1:
            # Vários equipamentos virariam o mesmo código
            conflitos.append((novo, lista))
            continue

        id_eq, antigo, nome = lista[0]

        # O novo código já existe em outro equipamento?
        existe = conexao.execute(
            "SELECT id, barcode, nome FROM equipamento "
            "WHERE barcode = ? AND id != ?",
            (novo, id_eq),
        ).fetchone()

        if existe:
            conflitos.append(
                (
                    novo,
                    lista
                    + [
                        (
                            existe["id"],
                            existe["barcode"],
                            "(já existente no sistema)",
                        )
                    ],
                )
            )
            continue

        atualizacoes.append((id_eq, antigo, novo))

    # ---------------------------------------------------------------
    # 4. Resumo antes de executar
    # ---------------------------------------------------------------

    print("-" * 70)
    print("RESUMO DA ANÁLISE")
    print("-" * 70)
    print(f"Já estavam com {TAMANHO} dígitos : {ja_ok}")
    print(f"Serão atualizados          : {len(atualizacoes)}")
    print(f"Conflitos (não alterados)  : {len(conflitos)}")

    if nao_numericos:
        print(f"Não numéricos (ignorados)  : {len(nao_numericos)}")

    print()

    if conflitos:

        print("!" * 70)
        print("ATENÇÃO - CONFLITOS ENCONTRADOS")
        print("!" * 70)

        for novo, lista in conflitos:

            print(f"\nCódigo final: {novo}")

            for id_eq, antigo, nome in lista:
                print(
                    f"   - ID {id_eq} | atual: {antigo} | {nome}"
                )

        print()
        print(
            "Esses equipamentos NÃO foram alterados, "
            "pois dois deles ficariam com o mesmo código."
        )
        print(
            "Resolva manualmente no sistema e rode "
            "o script novamente."
        )
        print()

    if not atualizacoes:

        print("Nada a atualizar.")

        if nao_numericos:

            print()
            print("Códigos não numéricos (ignorados):")

            for id_eq, codigo, nome in nao_numericos[:20]:
                print(
                    f"   - ID {id_eq} | [{codigo}] | {nome}"
                )

        conexao.close()
        input("\nPressione ENTER para sair...")
        return

    # ---------------------------------------------------------------
    # 5. Confirmação
    # ---------------------------------------------------------------

    print("Exemplos de alterações:")

    for id_eq, antigo, novo in atualizacoes[:10]:
        print(f"   ID {id_eq}: {antigo}  ->  {novo}")

    if len(atualizacoes) > 10:
        print(f"   ... e mais {len(atualizacoes) - 10}")

    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--confirmar":

        confirmou = True

    else:

        resposta = input(
            "Confirma a atualização? (S/N): "
        ).strip().upper()

        confirmou = resposta == "S"

    if not confirmou:

        print("Operação cancelada.")
        conexao.close()
        input("\nPressione ENTER para sair...")
        return

    # ---------------------------------------------------------------
    # 6. Backup automático
    # ---------------------------------------------------------------

    backup = pasta / (
        "patrimonio_backup_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".db"
    )

    shutil.copy2(str(caminho_db), str(backup))

    print()
    print(f"Backup criado: {backup.name}")

    # ---------------------------------------------------------------
    # 7. Executa as atualizações
    # ---------------------------------------------------------------

    executados = 0

    try:

        for id_eq, antigo, novo in atualizacoes:

            conexao.execute(
                "UPDATE equipamento SET barcode = ? "
                "WHERE id = ?",
                (novo, id_eq),
            )

            executados += 1

        conexao.commit()

    except Exception as erro:

        conexao.rollback()

        print()
        print("ERRO durante a atualização:")
        print(f"{type(erro).__name__}: {erro}")
        print("NENHUMA alteração foi aplicada.")

        conexao.close()
        input("\nPressione ENTER para sair...")
        return

    # ---------------------------------------------------------------
    # 8. Verificação final
    # ---------------------------------------------------------------

    restantes = conexao.execute(
        "SELECT COUNT(*) AS total FROM equipamento "
        "WHERE LENGTH(TRIM(barcode)) < ? "
        "AND TRIM(barcode) GLOB '[0-9]*'",
        (TAMANHO,),
    ).fetchone()["total"]

    conexao.close()

    print()
    print("=" * 70)
    print("NORMALIZAÇÃO CONCLUÍDA")
    print("=" * 70)
    print(f"Atualizados com sucesso : {executados}")
    print(f"Conflitos pendentes     : {len(conflitos)}")
    print(f"Códigos curtos restantes: {restantes}")
    print("=" * 70)

    if restantes:
        print()
        print(
            "Ainda existem códigos numéricos com menos "
            "de 6 dígitos. Rode novamente o script."
        )

    print()
    print("Lembrete: ligue o Flask novamente.")
    print()

    input("Pressione ENTER para sair...")


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print("Operação cancelada pelo usuário.")

    except Exception as erro:

        print()
        print("=" * 70)
        print("ERRO INESPERADO")
        print("=" * 70)
        print(f"{type(erro).__name__}: {erro}")
        input("\nPressione ENTER para sair...")
