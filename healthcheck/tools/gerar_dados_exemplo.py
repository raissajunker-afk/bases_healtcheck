"""Gerador de bases de exemplo (sintéticas) para validar o portal offline.

Cria CSVs com o mesmo formato esperado das bases reais, permitindo rodar o
pipeline completo sem dados sensíveis. Use `python main.py --demo`.

NÃO contém dados reais — apenas valores aleatórios plausíveis.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

GDS = ["GD Norte", "GD Sul", "GD Sudeste", "GD Centro-Oeste"]
SFS = ["Oncologia", "Especialidades", "Hospitalar", "Vacinas"]
FRANQUIAS = ["GI", "GU", "HN", "RESP", "IMUNO"]
ESPECIALIDADES = {
    "GI": ["ONCOLOGIA CLINICA", "GASTROENTEROLOGIA"],
    "GU": ["UROLOGIA", "ONCOLOGIA CLINICA"],
    "HN": ["CIRURGIA DE CABECA E PESCOCO", "ONCOLOGIA CLINICA"],
    "RESP": ["PNEUMOLOGIA", "ALERGOLOGIA"],
    "IMUNO": ["REUMATOLOGIA", "DERMATOLOGIA"],
}
CIDADES = [("SAO PAULO", "SP"), ("CAMPINAS", "SP"), ("RIO DE JANEIRO", "RJ"), ("BELO HORIZONTE", "MG"),
           ("CURITIBA", "PR"), ("PORTO ALEGRE", "RS"), ("SALVADOR", "BA"), ("RECIFE", "PE"),
           ("BRASILIA", "DF"), ("GOIANIA", "GO")]
CANAIS = ["F2F", "F2F", "F2F", "Remoto", "Digital"]
NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elaine", "Felipe", "Gabriela", "Hugo", "Isabela", "João",
         "Karina", "Lucas", "Marina", "Nelson", "Olivia", "Paulo", "Renata", "Sergio", "Tatiana", "Vitor"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Santos", "Pereira", "Lima", "Costa", "Ferreira", "Almeida", "Gomes"]


def _nome():
    return random.choice(NOMES) + " " + random.choice(SOBRENOMES)


def _write(path: Path, header: list[str], rows: list[list]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


def gerar(bases_dir: Path, n_consultores: int = 24, meses: int = 12):
    bases_dir.mkdir(parents=True, exist_ok=True)

    # consultores / estrutura
    consultores = []
    for i in range(n_consultores):
        cidade, uf = random.choice(CIDADES)
        consultores.append({
            "consultor": _nome() + f" {i+1:02d}",
            "sales_force": random.choice(SFS),
            "gd": random.choice(GDS),
            "cidade_sede": cidade,
            "uf_sede": uf,
            "tipo_setor": random.choice(["local", "viagem_interna", "viagem_interestadual"]),
            "painel_meta": random.randint(80, 160),
            "ativo": "sim" if random.random() > 0.05 else "afastado",
        })

    _write(bases_dir / "estrutura.csv",
           ["consultor", "sales_force", "gd", "cidade_sede", "uf_sede", "tipo_setor", "painel_meta", "ativo"],
           [[c["consultor"], c["sales_force"], c["gd"], c["cidade_sede"], c["uf_sede"], c["tipo_setor"], c["painel_meta"], c["ativo"]] for c in consultores])

    # painel (médicos por consultor)
    painel_rows = []
    medicos = []  # (mdm, crm, nome, esp, franquia, consultor, sf, gd, cidade, uf, mccp)
    mdm = 100000
    for c in consultores:
        n = random.randint(70, 140)
        for _ in range(n):
            mdm += 1
            fr = random.choice(FRANQUIAS)
            esp = random.choice(ESPECIALIDADES[fr])
            cidade, uf = random.choice(CIDADES)
            mccp = "1" if random.random() < 0.6 else "0"
            reg = {
                "mdm": mdm, "crm": f"CRM{random.randint(10000,99999)}", "nome_medico": "Dr(a). " + _nome(),
                "especialidade": esp, "franquia": fr, "consultor": c["consultor"],
                "sales_force": c["sales_force"], "gd": c["gd"], "cidade": cidade, "uf": uf, "no_mccp": mccp,
            }
            medicos.append(reg)
            painel_rows.append([reg["mdm"], reg["crm"], reg["nome_medico"], reg["especialidade"], reg["franquia"],
                                reg["consultor"], reg["sales_force"], reg["gd"], reg["cidade"], reg["uf"], reg["no_mccp"]])

    _write(bases_dir / "painel.csv",
           ["mdm", "crm", "nome_medico", "especialidade", "franquia", "consultor", "sales_force", "gd", "cidade", "uf", "no_mccp"],
           painel_rows)

    # visitas (12 meses)
    hoje = date.today().replace(day=1)
    inicio = (hoje - timedelta(days=meses * 30)).replace(day=1)
    visit_rows = []
    by_consultor = {}
    for m in medicos:
        by_consultor.setdefault(m["consultor"], []).append(m)

    for c in consultores:
        if c["ativo"] != "sim":
            continue
        lista = by_consultor.get(c["consultor"], [])
        if not lista:
            continue
        # ~cobertura entre 50% e 95%
        cobertos = random.sample(lista, k=int(len(lista) * random.uniform(0.5, 0.95)))
        for d_offset in range(meses):
            mes = (inicio.year + (inicio.month - 1 + d_offset) // 12, (inicio.month - 1 + d_offset) % 12 + 1)
            dias_mes = random.sample(range(1, 28), k=random.randint(14, 20))
            for dia in dias_mes:
                data = date(mes[0], mes[1], dia)
                for _ in range(random.randint(4, 9)):
                    med = random.choice(cobertos)
                    canal = random.choice(CANAIS)
                    visit_rows.append([
                        data.isoformat(), c["consultor"], c["sales_force"], c["gd"],
                        med["mdm"], med["crm"], med["nome_medico"], med["especialidade"], med["franquia"],
                        canal, med["cidade"], med["uf"], f"BR{random.randint(1,30):02d}",
                        "1", med["no_mccp"], "1" if random.random() < 0.7 else "0",
                    ])

    header_v = ["data", "consultor", "sales_force", "gd", "mdm", "crm", "nome_medico", "especialidade",
                "franquia", "canal", "cidade", "uf", "brick", "no_painel", "no_mccp", "planejado"]
    # divide por ano para simular relatorio_visitas_YY.csv
    por_ano = {}
    for r in visit_rows:
        ano = r[0][:4]
        por_ano.setdefault(ano, []).append(r)
    for ano, rows in por_ano.items():
        _write(bases_dir / f"relatorio_visitas_{ano[2:]}.csv", header_v, rows)

    # ausências
    aus_rows = []
    cats = [("Treinamento", "produtiva"), ("Reuniao Ciclo", "produtiva"), ("Ferias", "pessoal"),
            ("Atestado", "pessoal"), ("Congresso", "produtiva")]
    for c in consultores:
        for _ in range(random.randint(1, 5)):
            cat = random.choice(cats)
            ini = inicio + timedelta(days=random.randint(0, meses * 28))
            dias = random.randint(1, 8)
            fim = ini + timedelta(days=dias - 1)
            aus_rows.append([c["consultor"], c["sales_force"], c["gd"], ini.isoformat(), fim.isoformat(), dias, cat[1], cat[0]])
    _write(bases_dir / "ausencias_de_campo_visao_geral.csv",
           ["consultor", "sales_force", "gd", "data_inicio", "data_fim", "dias", "categoria", "tipo"],
           aus_rows)

    # franquias_especialidades
    gerar_franquias(bases_dir)

    print(f"  bases de exemplo geradas: {len(consultores)} consultores, {len(medicos)} médicos, {len(visit_rows)} visitas.")


def gerar_franquias(bases_dir: Path):
    path = bases_dir / "franquias_especialidades.csv"
    rows = [
        ["GI", "ONCOLOGIA CLINICA", "alta", "1.0", "decisor", "Especialidade central"],
        ["GI", "GASTROENTEROLOGIA", "alta", "1.0", "influenciador", "Especialidade relevante"],
        ["GU", "UROLOGIA", "alta", "1.0", "decisor", "Especialidade prioritaria"],
        ["GU", "ONCOLOGIA CLINICA", "alta", "1.0", "decisor", "Especialidade central"],
        ["HN", "CIRURGIA DE CABECA E PESCOCO", "alta", "1.0", "decisor", "Especialidade prioritaria"],
        ["HN", "ONCOLOGIA CLINICA", "media", "0.8", "influenciador", ""],
        ["RESP", "PNEUMOLOGIA", "alta", "1.0", "decisor", ""],
        ["RESP", "ALERGOLOGIA", "media", "0.7", "influenciador", ""],
        ["IMUNO", "REUMATOLOGIA", "alta", "1.0", "decisor", ""],
        ["IMUNO", "DERMATOLOGIA", "media", "0.8", "influenciador", ""],
    ]
    _write(path, ["franquia", "especialidade", "relevancia", "peso", "papel", "observacao"], rows)


if __name__ == "__main__":
    import sys
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "bases"
    gerar(destino)
