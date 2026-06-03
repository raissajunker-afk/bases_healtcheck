"""Módulo de Painel.

Constrói a hierarquia (consultor -> Sales Force -> GD), o território de cada
consultor e o snapshot de painel (médicos atribuídos a cada consultor).

Contrato:
    painel = processar_painel(bases)

Retorna dict com:
    consultores : dict[chave_consultor] -> atributos de estrutura/território
    medicos     : dict[chave_mdm]       -> atributos cadastrais do médico no painel
    origem_painel : "base_painel" | "derivado_visitas" | "vazio"
"""

from __future__ import annotations

import config
from processing import util


def _chave_consultor(nome) -> str:
    return util.norm_key(nome)


def _chave_medico(mdm, crm, nome) -> str:
    base = util.norm_key(mdm) or util.norm_key(crm) or util.norm_key(nome)
    return base


def processar_painel(bases: dict) -> dict:
    estrutura = bases.get("estrutura", [])
    painel_rows = bases.get("painel", [])
    visitas = bases.get("visitas", [])

    consultores: dict[str, dict] = {}

    def upsert_consultor(nome, sf=None, gd=None, **extra):
        chave = _chave_consultor(nome)
        if not chave:
            return None
        c = consultores.setdefault(
            chave,
            {
                "chave": chave,
                "consultor": util.norm_text(nome),
                "sales_force": "",
                "gd": "",
                "cidade_sede": "",
                "uf_sede": "",
                "tipo_setor": "",
                "painel_meta": 0,
                "ativo": True,
                "painel": 0,
            },
        )
        if sf and not c["sales_force"]:
            c["sales_force"] = util.norm_text(sf)
        if gd and not c["gd"]:
            c["gd"] = util.norm_text(gd)
        for k, v in extra.items():
            if v not in (None, "") and not c.get(k):
                c[k] = v
        return c

    # 1) Estrutura formal (fonte primária de hierarquia/território)
    for row in estrutura:
        c = upsert_consultor(
            row.get("consultor"),
            row.get("sales_force"),
            row.get("gd"),
            cidade_sede=util.norm_text(row.get("cidade_sede")),
            uf_sede=util.norm_text(row.get("uf_sede")),
            tipo_setor=util.norm_text(row.get("tipo_setor")),
        )
        if c is not None:
            if row.get("painel_meta") not in (None, ""):
                c["painel_meta"] = util.to_int(row.get("painel_meta"))
            ativo_val = row.get("ativo")
            if ativo_val not in (None, ""):
                nk = util.norm_key(ativo_val)
                # "afastado"/"inativo"/"nao" => inativo
                c["ativo"] = nk not in {"afastado", "inativo", "nao", "n", "0", "false", "desligado"}

    # 2) Snapshot de painel (médicos)
    medicos: dict[str, dict] = {}
    origem = "vazio"

    def upsert_medico(mdm, crm, nome, **attrs):
        chave = _chave_medico(mdm, crm, nome)
        if not chave:
            return None
        m = medicos.setdefault(
            chave,
            {
                "chave": chave,
                "mdm": util.norm_text(mdm),
                "crm": util.norm_text(crm),
                "nome_medico": util.norm_text(nome),
                "especialidade": "",
                "especialidade_sec": "",
                "franquia": "",
                "no_mccp": False,
                "consultor": "",
                "sales_force": "",
                "gd": "",
                "cidade": "",
                "uf": "",
                "brick": "",
                "no_painel": True,
            },
        )
        for k, v in attrs.items():
            if isinstance(v, bool):
                m[k] = m.get(k) or v
            elif v not in (None, "") and not m.get(k):
                m[k] = util.norm_text(v) if isinstance(v, str) else v
        return m

    if painel_rows:
        origem = "base_painel"
        for row in painel_rows:
            cons = util.norm_text(row.get("consultor"))
            sf = util.norm_text(row.get("sales_force"))
            gd = util.norm_text(row.get("gd"))
            upsert_consultor(cons, sf, gd)
            upsert_medico(
                row.get("mdm"),
                row.get("crm"),
                row.get("nome_medico"),
                especialidade=util.norm_text(row.get("especialidade")),
                especialidade_sec=util.norm_text(row.get("especialidade_sec")),
                franquia=util.norm_text(row.get("franquia")),
                no_mccp=util.to_bool(row.get("no_mccp")),
                consultor=cons,
                sales_force=sf,
                gd=gd,
                cidade=util.norm_text(row.get("cidade")),
                uf=util.norm_text(row.get("uf")),
                brick=util.norm_text(row.get("brick")),
            )
    elif visitas:
        # Deriva painel a partir das visitas: cada par médico-consultor visto
        # vira painel "de fato". no_mccp herda a flag se existir na visita.
        origem = "derivado_visitas"
        for row in visitas:
            if not util.to_bool(row.get("no_painel")) and "no_painel" in row and row.get("no_painel") is not None:
                # explicitamente fora de painel -> não entra no snapshot
                continue
            cons = util.norm_text(row.get("consultor"))
            sf = util.norm_text(row.get("sales_force"))
            gd = util.norm_text(row.get("gd"))
            upsert_consultor(cons, sf, gd)
            upsert_medico(
                row.get("mdm"),
                row.get("crm"),
                row.get("nome_medico"),
                especialidade=util.norm_text(row.get("especialidade")),
                especialidade_sec=util.norm_text(row.get("especialidade_sec")),
                franquia=util.norm_text(row.get("franquia")),
                no_mccp=util.to_bool(row.get("no_mccp")),
                consultor=cons,
                sales_force=sf,
                gd=gd,
                cidade=util.norm_text(row.get("cidade")),
                uf=util.norm_text(row.get("uf")),
                brick=util.norm_text(row.get("brick")),
            )

    # 3) Tamanho do painel por consultor
    contagem_painel: dict[str, int] = {}
    for m in medicos.values():
        ck = _chave_consultor(m.get("consultor"))
        if ck:
            contagem_painel[ck] = contagem_painel.get(ck, 0) + 1
    for ck, qtd in contagem_painel.items():
        if ck in consultores:
            consultores[ck]["painel"] = qtd

    return {
        "consultores": consultores,
        "medicos": medicos,
        "origem_painel": origem,
    }
