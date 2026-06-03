"""
processar.py — Healthcheck Operacional MSD Oncologia
====================================================

Lê fontes brutas, deduplica, calcula KPIs por consultor e gera payload.json
para o gerar_html.py consumir.

Fontes esperadas (no diretório do script):
  - estrutura.xlsx                       (estrutura organizacional, todas BUs)
  - ausencias_de_campo_visao_geral.csv   (TOT bruto, SEM deduplicação prévia)
  - relatorio_visitas_24.csv             (visitas ano fiscal 2024)
  - relatorio_visitas_25.csv             (visitas ano fiscal 2025)
  - relatorio_visitas_26.csv             (visitas ano fiscal 2026, parcial)

Saídas:
  - payload.json                  (consumido pelo gerar_html.py)
  - dedup_audit.csv               (registros removidos na deduplicação de ausências)
  - tipo_setor_audit.csv          (justificativa da classificação de cada consultor)
  - processar_log.txt             (log de execução com totais)

PARAMETRIZAÇÃO POR BU:
  Mude `BU_ALVO` no topo. O resto do código é agnóstico.
"""

import os
import json
import re
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
from collections import defaultdict, Counter
from io import StringIO

# ============================================================================
# CONFIG
# ============================================================================
BU_ALVO = 'ONCOLOGIA'        # filtra estrutura.xlsx
BU_LABEL = 'ONCOLOGIA PAN-TUMOR'  # label no dashboard (exclui SFs abaixo)
HIERARCHY_FILTRO = 'REP'     # universo de análise = REPs (gerentes não executam)

# ============================================================================
# SALES FORCES EXCLUÍDAS — removidas de TODO o universo de análise.
# Consultores dessas SFs NÃO entram em nenhum cálculo, KPI, ranking, histograma,
# série, overlap ou tabela. É como se não existissem no payload.
# Motivo: enviesam resultados e complicam a leitura do pan-tumor.
# Inclui nomes pré-fusão (BR_HEMATO, BR_TRANSPLANTE) para limpar histórico.
# ============================================================================
SFS_EXCLUIDAS = {
    'BR_ENCAMINHADORES',
    'BR_HEMATO_TRANSPLANTE',
    'BR_HEMATO',           # pré-fusão → virou BR_HEMATO_TRANSPLANTE
    'BR_TRANSPLANTE',      # pré-fusão → virou BR_HEMATO_TRANSPLANTE
}

# ============================================================================
# CONSULTORES AFASTADOS — entram no payload com flag `afastado=True`.
# O gerar_html.py exclui esses ISIDs de:
#   - médias/medianas do time e SF
#   - histogramas e distribuições
#   - rankings (Top alta/queda, Top fora painel, Variabilidade, etc.)
#   - análises de correlação
#   - curva tempo no setor × cobertura
# Mantém-os apenas na tabela Detalhe (com tag visual "Afastado") e como par
# em Overlap (com flag visual no par).
# Pra adicionar/remover: edite o dict abaixo. O motivo aparece em tooltips.
# ============================================================================
ISIDS_AFASTADOS = {
    'SACOMAN':   {'motivo': 'Afastamento em 2026', 'periodo': 'a partir de 2026-Q1'},
    'CECCHIAN':  {'motivo': 'Afastamento de longa duração (job)', 'periodo': 'desde set/2025'},
    'DEOLMARI':  {'motivo': 'Em job prolongado', 'periodo': 'sem visitas no MAT'},
}

# ============================================================================
# CAMINHOS DOS ARQUIVOS — bases (input) e outputs (saídas)
# ============================================================================
# Caminhos preferenciais (OneDrive MSD). Se não existirem, faz fallback pra pasta atual.
_BASES_PREF = r'C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases'
_OUT_PREF   = r'C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck'

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BASES_FALLBACK = os.path.join(_SCRIPT_DIR, 'bases')
_OUT_FALLBACK = _SCRIPT_DIR

BASES_DIR = _BASES_PREF if os.path.isdir(_BASES_PREF) else _BASES_FALLBACK
OUT_DIR   = _OUT_PREF   if os.path.isdir(_OUT_PREF)   else _OUT_FALLBACK

# Helpers pra montar caminho de input/output

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO COBERTURA DE PAINEL  (ICP-F2F · ICP-Multi · Série Painel×Visitas)
# ══════════════════════════════════════════════════════════════════════════════
# HCP alvo = painel (snapshot ≤ mes_fechado) ∩ MCCP (meta>0 no quarter).
# ICP-F2F   = HCPs alvo com ≥1 interação F2F   / HCPs alvo × 100
# ICP-Multi = HCPs alvo com ≥1 canal qualquer  / HCPs alvo × 100
# ══════════════════════════════════════════════════════════════════════════════
import re as _re_cob
from collections import defaultdict as _dd_cob

_CANAL_F2F = "face to face"
_CANAIS_MC = {
    "face to face","engage","remote call","remote detail",
    "ae","adverse event","sms","chat","text","email with product",
}

def _qde(dt):
    return (dt.year, (dt.month-1)//3+1)

def _norm_mdm(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if not s or s.upper() in ("NAN", "NONE"):
        return None
    if _re_cob.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s.upper()

def _parse_ciclo(s):
    s = str(s).strip()
    m = _re_cob.match(r"^MCC-BR-(\d{4})-(Q\d)[_ ]+BR[_ ]+([A-Z0-9]+)[_ ]+([A-Z0-9]+)$", s, flags=_re_cob.I)
    if m:
        return (m.group(1), m.group(2), m.group(3).upper(), m.group(4).upper())

    m = _re_cob.match(r"^MCC-BR-(\d{4})-(Q\d)", s, flags=_re_cob.I)
    if m:
        return (m.group(1), m.group(2), None, None)

    return (None, None, None, None)

def _read_flex(path, usecols=None):
    for enc in ("utf-8","latin-1","utf-8-sig"):
        try:
            chunks=[]
            kw=dict(sep=";",encoding=enc,dtype=str,low_memory=False)
            if usecols: kw["usecols"]=usecols
            for ck in pd.read_csv(path, chunksize=50_000, **kw):
                ck.columns=[c.strip().lstrip("\ufeff") for c in ck.columns]
                chunks.append(ck)
            return pd.concat(chunks,ignore_index=True) if chunks else pd.DataFrame()
        except Exception:
            continue
    return pd.DataFrame()

def _ler_painel_cob(path, isids=None):
    df=_read_flex(path,["SNAPSHOT_DATE","MDM CONTA","ISID CONSULTOR"])
    if df.empty: return df
    df["ISID CONSULTOR"]=df["ISID CONSULTOR"].str.upper().str.strip()
    df["MDM CONTA"]=df["MDM CONTA"].str.strip()
    if isids: df=df[df["ISID CONSULTOR"].isin(isids)]
    df["_snap"]=pd.to_datetime(df["SNAPSHOT_DATE"],format="%d/%m/%Y",errors="coerce")
    return df

def _ler_mccp_cob(path, isids=None):
    cols = [
        "Plano de ciclo: Plano de ciclo multicanal",
        "ACC MDM ID",
        "Canal",
        "Interações do canal - meta",
        "Interações do canal - reais",
        "ISID",
    ]

    df = _read_flex(path, cols)
    if df.empty:
        return df

    if "ISID" not in df.columns:
        df["ISID"] = None

    df["ISID"] = df["ISID"].astype(str).str.upper().str.strip()
    df["ACC MDM ID"] = df["ACC MDM ID"].map(_norm_mdm)

    parsed = df["Plano de ciclo: Plano de ciclo multicanal"].apply(
        lambda x: pd.Series(_parse_ciclo(x))
    )
    df["_ano"] = parsed[0]
    df["_q"] = parsed[1]
    df["_territorio_ciclo"] = parsed[2]
    df["_isid_ciclo"] = parsed[3]

    df.loc[df["ISID"].isin(["", "NAN", "NONE"]), "ISID"] = df["_isid_ciclo"]
    df["ISID"] = df["ISID"].astype(str).str.upper().str.strip()

    if isids:
        df = df[df["ISID"].isin(isids)]

    for col, key in [
        ("_meta", "Interações do canal - meta"),
        ("_reais", "Interações do canal - reais"),
    ]:
        df[col] = (
            df[key]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    df["_canal"] = df["Canal"].astype(str).str.strip()

    return df

def calcular_cobertura_painel(path_painel,path_mccp,universo_isids=None,mesfechado=None):
    if not(os.path.exists(path_painel) and os.path.exists(path_mccp)):
        print("  [ICP] painel/mccp não encontrado."); return pd.DataFrame()
    print("  [ICP] lendo painel...",end=" ",flush=True)
    df_p=_ler_painel_cob(path_painel,universo_isids); print(f"{len(df_p):,}")
    print("  [ICP] lendo mccp...",end=" ",flush=True)
    df_m=_ler_mccp_cob(path_mccp,universo_isids);    print(f"{len(df_m):,}")
    if df_p.empty or df_m.empty: return pd.DataFrame()
    snaps=df_p["_snap"].dropna().unique()
    if mesfechado is not None:
        # mesfechado é o 1º dia do mês — converter para último dia do mês
        _mf = pd.Timestamp(mesfechado) + pd.offsets.MonthEnd(0)
        snaps=[s for s in snaps if s<=_mf]
    if not len(snaps): print("  [ICP] sem snapshots."); return pd.DataFrame()
    snap=max(snaps); ano,qn=_qde(snap); qs=f"Q{qn}"
    print(f"  [ICP] snap={snap.date()} → {ano}-{qs}")
    df_snap=(df_p[df_p["_snap"]==snap][["ISID CONSULTOR","MDM CONTA"]]
             .drop_duplicates().rename(columns={"ISID CONSULTOR":"ISID","MDM CONTA":"MDM"}))
    df_q=(df_m[(df_m["_ano"]==str(ano))&(df_m["_q"]==qs)&(df_m["_meta"]>0)]
          [["ISID","ACC MDM ID"]].drop_duplicates().rename(columns={"ACC MDM ID":"MDM"}))
    # Garantir que o alvo seja a interseção entre o painel oficial e o MCCP meta > 0
    alvo=df_snap.merge(df_q,on=["ISID","MDM"],how="inner")
    hcps_alvo=alvo.groupby("ISID")["MDM"].apply(set).to_dict()
    dfi=(df_m[(df_m["_ano"]==str(ano))&(df_m["_q"]==qs)&(df_m["_reais"]>0)]
         [["ISID","ACC MDM ID","_canal"]].copy()
         .rename(columns={"ACC MDM ID":"MDM","_canal":"CANAL"}))
    f2f_s=(dfi[dfi["CANAL"].apply(lambda c:_CANAL_F2F in str(c).lower())]
           [["ISID","MDM"]].drop_duplicates().groupby("ISID")["MDM"].apply(set).to_dict())
    mc_s =(dfi[dfi["CANAL"].apply(lambda c:any(k in str(c).lower() for k in _CANAIS_MC))]
           [["ISID","MDM"]].drop_duplicates().groupby("ISID")["MDM"].apply(set).to_dict())
    rows=[]
    for isid in set(hcps_alvo)|set(f2f_s)|set(mc_s):
        av=hcps_alvo.get(isid,set()); f2=f2f_s.get(isid,set())&av; mc=mc_s.get(isid,set())&av
        n=len(av)
        rows.append({"ISID":isid,"hcpsAlvoTotal":n,
            "hcpsCobertosF2F":len(f2),"hcpsCobertosMulti":len(mc),
            "pctCoberturaF2F":round(len(f2)/n*100,1) if n else 0.0,
            "pctCoberturaMulti":round(len(mc)/n*100,1) if n else 0.0,
            "mdmsAlvo":sorted(av),"mdmsCobertosF2F":sorted(f2),"mdmsCobertosMulti":sorted(mc),
            "snapRefCobertura":str(snap.date()),"quarterRefCobertura":f"{ano}-{qs}"})
    df_r=pd.DataFrame(rows)
    if len(df_r):
        print(f"  [ICP] {len(df_r)} ISIDs | F2F={df_r['pctCoberturaF2F'].mean():.1f}% | Multi={df_r['pctCoberturaMulti'].mean():.1f}%")
    return df_r

def enriquecer_cobertura_global(dfmetr: pd.DataFrame, df_cob: pd.DataFrame) -> pd.DataFrame:
    """Merge df_cob no dfmetr, adicionando todos os campos de cobertura."""
    cols_defs = [
        ("hcpsAlvoTotal", 0), ("hcpsCobertosF2F", 0), ("hcpsCobertosMulti", 0),
        ("pctCoberturaF2F", 0.0), ("pctCoberturaMulti", 0.0),
        ("mdmsAlvo", None), ("mdmsCobertosF2F", None), ("mdmsCobertosMulti", None),
        ("snapRefCobertura", None), ("quarterRefCobertura", None),
    ]
    if df_cob.empty:
        for col, default in cols_defs:
            if col.startswith("mdms"):
                dfmetr[col] = [[] for _ in range(len(dfmetr))]
            else:
                dfmetr[col] = default
        return dfmetr
    
    # Se df_cob não está vazio, faz o merge
    dfmetr = dfmetr.merge(df_cob, on="ISID", how="left")
    
    # Preencher NaNs após merge para garantir que as colunas existam e tenham tipos corretos
    for col, default in cols_defs:
        if col not in dfmetr.columns:
            if col.startswith("mdms"):
                dfmetr[col] = [[] for _ in range(len(dfmetr))]
            else:
                dfmetr[col] = default
        else:
            if col.startswith("mdms"):
                # Para colunas de lista, o fillna(default) não funciona bem se default for []
                # Usamos loc para preencher apenas onde é nulo
                mask = dfmetr[col].isna()
                dfmetr.loc[mask, col] = pd.Series([[] for _ in range(mask.sum())], index=dfmetr.index[mask])
            else:
                dfmetr[col] = dfmetr[col].fillna(default)
    
    # Bugfix: Se mdmsAlvo foi criado anteriormente em df_metr (ex: no loop de consultores),
    # o merge cria mdmsAlvo_x e mdmsAlvo_y. Precisamos garantir que mdmsAlvo seja único.
    if 'mdmsAlvo_y' in dfmetr.columns:
        # Priorizar dados do df_cob (suffix _y) se não forem nulos/vazios
        for base in ["mdmsAlvo", "mdmsCobertosF2F", "mdmsCobertosMulti"]:
            col_x, col_y = f"{base}_x", f"{base}_y"
            if col_x in dfmetr.columns and col_y in dfmetr.columns:
                # Onde _y tem dado (lista não vazia), usa _y. Senão usa _x.
                dfmetr[base] = dfmetr.apply(lambda r: r[col_y] if (isinstance(r[col_y], list) and len(r[col_y]) > 0) else r[col_x], axis=1)
                dfmetr.drop(columns=[col_x, col_y], inplace=True)

    return dfmetr

def calcular_serie_painel_visitas(paths_vis,path_painel,path_mccp,
                                   win_isid_map,universo_isids=None,
                                   data_ini=None,data_fim=None):
    if isinstance(paths_vis,str): paths_vis=[paths_vis]
    cols_v=["USR WIN ID","CALL DATE","CALL SUB TYPE","CALL STATUS","ACC MDM ID","ACC TYPE"]
    dfs=[]
    for p in paths_vis:
        if not os.path.exists(p): continue
        df=_read_flex(p); df=df[[c for c in cols_v if c in df.columns]].copy()
        if "CALL STATUS"   in df.columns: df=df[df["CALL STATUS"].str.strip()=="Submitted_vod"]
        if "CALL SUB TYPE" in df.columns: df=df[df["CALL SUB TYPE"].str.strip()=="F2F"]
        if "ACC TYPE"      in df.columns: df=df[df["ACC TYPE"].str.strip()=="Person Account"]
        df["_data"]=pd.to_datetime(df.get("CALL DATE",pd.Series(dtype=str)),format="%d/%m/%Y",errors="coerce")
        df["_win"]=pd.to_numeric(df.get("USR WIN ID",pd.Series(dtype=str)),errors="coerce")
        df["_mdm"]=df.get("ACC MDM ID",pd.Series(dtype=str)).astype(str).str.strip()
        dfs.append(df)
    if not dfs: print("  [SERIE_PV] sem visitas."); return []
    df_vis=pd.concat(dfs,ignore_index=True)
    df_vis["_ISID"]=df_vis["_win"].map(win_isid_map)
    df_vis=df_vis.dropna(subset=["_ISID","_data","_mdm"])
    if universo_isids: df_vis=df_vis[df_vis["_ISID"].isin(universo_isids)]
    if data_ini: df_vis=df_vis[df_vis["_data"]>=pd.Timestamp(data_ini)]
    if data_fim:
        # data_fim é o 1º dia do mês fechado — converter para último dia do mês
        _dfim = pd.Timestamp(data_fim)
        _dfim_eom = _dfim + pd.offsets.MonthEnd(0)
        df_vis=df_vis[df_vis["_data"]<=_dfim_eom]
    if df_vis.empty: return []
    df_vis["_ym"]=df_vis["_data"].dt.to_period("M").astype(str)
    df_vis["_ano"]=df_vis["_data"].dt.year; df_vis["_mes"]=df_vis["_data"].dt.month
    df_p=_ler_painel_cob(path_painel,universo_isids)
    pan_snaps={}
    if not df_p.empty:
        for(isid,snap),grp in df_p.groupby(["ISID CONSULTOR","_snap"]):
            pan_snaps[(isid,snap)]=set(grp["MDM CONTA"].dropna().str.strip())
    df_m=_ler_mccp_cob(path_mccp,universo_isids)
    mccp_alvo=_dd_cob(set)
    if not df_m.empty:
        sub=df_m[(df_m["_meta"]>0)&df_m["_ano"].notna()&df_m["_q"].notna()]
        for _,row in sub[["ISID","ACC MDM ID","_ano","_q"]].iterrows():
            mccp_alvo[(row["ISID"],row["_ano"],row["_q"])].add(row["ACC MDM ID"])
    rows=[]
    for(isid,ym),grp in df_vis.groupby(["_ISID","_ym"]):
        ano=int(grp["_ano"].iloc[0]); mes=int(grp["_mes"].iloc[0]); qs=f"Q{(mes-1)//3+1}"
        snap_ts=pd.Timestamp(ano,mes,1)
        si=[s for(i,s) in pan_snaps if i==isid and s<=snap_ts]
        mdms_p=pan_snaps.get((isid,max(si)),set()) if si else set()
        mdms_q=mccp_alvo.get((isid,str(ano),qs),set())
        mdms_a=mdms_p&mdms_q; vt=len(grp); vn=int(grp["_mdm"].isin(mdms_a).sum())
        rows.append({"ISID":isid,"ym":ym,"vis_total":vt,"vis_no_painel":vn,
            "vis_fora_painel":vt-vn,"pct_no_painel":round(vn/vt*100,1) if vt else 0.0,
            "dias_visita":int(grp["_data"].dt.normalize().nunique()),
            "mdms_alvo_mes":len(mdms_a)})
    print(f"  [SERIE_PV] {len(rows)} registros ISID×mês"); return rows

def _agregar_serie_pv_time(serie):
    agg=_dd_cob(lambda:{"vis_total":0,"vis_no_painel":0,"vis_fora_painel":0,"n":0})
    for r in serie:
        d=agg[r["ym"]]; d["vis_total"]+=r["vis_total"]
        d["vis_no_painel"]+=r["vis_no_painel"]; d["vis_fora_painel"]+=r["vis_fora_painel"]; d["n"]+=1
    out=[]
    for ym in sorted(agg):
        d=agg[ym]; t=d["vis_total"]
        out.append({"ym":ym,"vis_total":t,"vis_no_painel":d["vis_no_painel"],
            "vis_fora_painel":d["vis_fora_painel"],
            "pct_no_painel":round(d["vis_no_painel"]/t*100,1) if t else 0,
            "n_consultores":d["n"]})
    return out
# ══════════════════════════════════════════════════════════════════════════════

def IN(filename):
    """Caminho de arquivo de input (na pasta bases)."""
    return os.path.join(BASES_DIR, filename)

def OUT(filename):
    """Caminho de arquivo de output (na pasta de saída)."""
    return os.path.join(OUT_DIR, filename)

print(f"[CAMINHOS]")
print(f"  Bases (input):   {BASES_DIR}")
print(f"  Outputs (saída): {OUT_DIR}")
if BASES_DIR == '.':
    print(f"  ⚠ Bases usando pasta atual (caminho OneDrive não acessível)")
if OUT_DIR == '.':
    print(f"  ⚠ Outputs usando pasta atual (caminho OneDrive não acessível)")
print()

# Datas de referência
HOJE = date.today()
MES_ATUAL = date(HOJE.year, HOJE.month, 1)
# Último mês fechado = mês anterior ao corrente
if HOJE.month == 1:
    MES_FECHADO = date(HOJE.year - 1, 12, 1)
else:
    MES_FECHADO = date(HOJE.year, HOJE.month - 1, 1)

# Mês corrente PARCIAL (em andamento) — usado em séries pra mostrar o "como está agora"
# sem bagunçar métricas MAT que são calculadas só em meses fechados.
MES_PARCIAL = MES_ATUAL
INCLUIR_MES_PARCIAL = True  # se True, séries temporais incluem o mês corrente marcado como parcial

# Janela MAT = 12 meses fechados
JANELA_FIM = MES_FECHADO
JANELA_INI = date(JANELA_FIM.year - 1, JANELA_FIM.month, 1) if JANELA_FIM.month != 12 \
             else date(JANELA_FIM.year, 1, 1)
# Recalcular: 12 meses incluindo o último fechado
ano_ini = JANELA_FIM.year - 1 if JANELA_FIM.month < 12 else JANELA_FIM.year
mes_ini = (JANELA_FIM.month % 12) + 1
if mes_ini == 1 and JANELA_FIM.month == 12:
    ano_ini = JANELA_FIM.year
JANELA_INI = date(ano_ini, mes_ini, 1)

# Meta default
META_PAINEL_DEFAULT = 120
META_VIS_DIA_DEFAULT = 6

# Dias úteis ano farma (252 = MSD)
DIAS_UTEIS_ANO_FARMA = 252
ANO_FIM_FARMA = '20/12'

# Categorias de ausência
CAT_VIAGEM = 'Deslocamento (viagem)'
CAT_REUNIAO = 'Reunião/Escritório'
CAT_CONGRESSO = 'Congresso/Simpósio'
CAT_TREINAMENTO = 'Treinamento'
CAT_GESTAO = 'Gestão do Território'
CAT_PESSOAL = 'Motivo Pessoal'
CAT_OUTROS = 'Outros'

# Mapeamento subtipo → categoria
SUBTIPOS = {
    'Viagem': CAT_VIAGEM,
    'Reuniões Nacionais': CAT_REUNIAO,
    'Reuniões de equipe': CAT_REUNIAO,
    'Reuniões Regionais': CAT_REUNIAO,
    'Escritório': CAT_REUNIAO,
    'Congressos / Simpósios': CAT_CONGRESSO,
    'Treinamento': CAT_TREINAMENTO,
    'Gestão do Território': CAT_GESTAO,
    'Férias / licença anual': CAT_PESSOAL,
    'Licença por doença': CAT_PESSOAL,
    'Licença parental': CAT_PESSOAL,
    'Incapacidade': CAT_PESSOAL,
    'Dia Compensatório': CAT_PESSOAL,
    'Meio Período de Trabalho': CAT_PESSOAL,
    'Outras ausências pessoais aprovadas': CAT_PESSOAL,
    'Outras ausências de negócios aprovadas': CAT_REUNIAO,  # tratamos como reunião/escritório
    'Day off': CAT_PESSOAL,
    # 'Feriado público' é removido (já descontado do dias úteis)
}

# Classificação produtivo vs improdutivo (slot de visita)
# Produtivo = é trabalho, mas reduz slot de visita
# Improdutivo = não é trabalho (afasta da empresa)
CAT_PRODUTIVAS = {CAT_VIAGEM, CAT_REUNIAO, CAT_CONGRESSO, CAT_TREINAMENTO, CAT_GESTAO}
CAT_IMPRODUTIVAS = {CAT_PESSOAL}

# Equivalência de duração → fração de dia
EQUIV_DUR = {
    'Dia Inteiro': 1.0,
    'Durante a Manhã': 0.5,
    'Durante a Tarde': 0.5,
    'Início da Manhã': 0.25,
    'Final da Manhã': 0.25,
    'Início da Tarde': 0.25,
    'Final da Tarde': 0.25,
}

# Prioridade R3 (subtipos no mesmo dia/duração — qual mantém)
PRIORIDADE_SUBTIPO = {
    'Férias / licença anual': 10,
    'Licença por doença': 10,
    'Licença parental': 10,
    'Incapacidade': 10,
    'Dia Compensatório': 9,
    'Outras ausências pessoais aprovadas': 8,
    'Day off': 8,
    'Treinamento': 7,
    'Congressos / Simpósios': 6,
    'Reuniões Nacionais': 5,
    'Reuniões Regionais': 5,
    'Reuniões de equipe': 5,
    'Viagem': 4,
    'Escritório': 3,
    'Outras ausências de negócios aprovadas': 3,
    'Gestão do Território': 2,
}

# Regras de classificação tipo_setor (comportamento real, MAT)
TIPO_LOCAL_MAX_CIDADES = 10
TIPO_LOCAL_MAX_UFS = 1
TIPO_VIAGEM_MIN_CIDADES = 30
TIPO_VIAGEM_MIN_UFS = 3


# ============================================================================
# CALENDÁRIO — feriados, pontes, carnaval (3 anos)
# ============================================================================
FERIADOS_OFICIAIS = [
    # 2024
    date(2024,1,1), date(2024,2,13), date(2024,2,14),
    date(2024,3,29), date(2024,4,21), date(2024,5,1),
    date(2024,5,30), date(2024,9,7), date(2024,10,12),
    date(2024,11,2), date(2024,11,15), date(2024,11,20),
    date(2024,12,25),
    # 2025
    date(2025,1,1), date(2025,3,4), date(2025,3,5),
    date(2025,4,18), date(2025,4,21), date(2025,5,1),
    date(2025,6,19), date(2025,9,7), date(2025,10,12),
    date(2025,11,2), date(2025,11,15), date(2025,11,20),
    date(2025,12,25),
    # 2026
    date(2026,1,1), date(2026,2,17), date(2026,2,18),
    date(2026,4,3), date(2026,4,21), date(2026,5,1),
    date(2026,6,4), date(2026,9,7), date(2026,10,12),
    date(2026,11,2), date(2026,11,15), date(2026,11,20),
    date(2026,12,25),
]

def _gerar_pontes(feriados):
    p = set()
    for f in feriados:
        if f.weekday() == 3: p.add(f + timedelta(days=1))   # Qui → Sex
        elif f.weekday() == 1: p.add(f - timedelta(days=1))  # Ter → Seg
    return p

def _semana_carnaval(ano):
    terca = {2024:date(2024,2,13), 2025:date(2025,3,4), 2026:date(2026,2,17)}.get(ano)
    if not terca: return set()
    seg = terca - timedelta(days=1)
    return {seg + timedelta(days=i) for i in range(5)}

FERIADOS_SET = set(FERIADOS_OFICIAIS)
PONTES_SET = _gerar_pontes(FERIADOS_OFICIAIS)
CARNAVAL_SET = set()
for a in [2024,2025,2026]:
    CARNAVAL_SET |= _semana_carnaval(a)
DIAS_NAO_UTEIS = FERIADOS_SET | PONTES_SET | CARNAVAL_SET

def eh_dia_util(d):
    if isinstance(d, pd.Timestamp): d = d.date()
    return d.weekday() < 5 and d not in DIAS_NAO_UTEIS

def dias_uteis_mes(ano, mes):
    ini = date(ano, mes, 1)
    fim = date(ano+1, 1, 1) if mes == 12 else date(ano, mes+1, 1)
    dias = pd.bdate_range(start=ini, end=fim - pd.Timedelta(days=1), freq='B')
    return sum(1 for d in dias if d.date() not in DIAS_NAO_UTEIS)

def fmt_ym(ano, mes):
    return f"{int(ano):04d}-{int(mes):02d}"

def fmt_ym_pt(ano, mes):
    return f"{int(mes):02d}/{int(ano):04d}"

# ============================================================================
# 1. LEITURA DA ESTRUTURA.XLSX
# ============================================================================
def ler_estrutura(path=None, bu=BU_ALVO):
    if path is None:
        path = IN('estrutura.xlsx')
    """
    Lê estrutura.xlsx e retorna 2 dataframes:
      - df_universo: linhas onde ACC HIERARCHY LEVEL == REP, filtro BU
      - df_full: estrutura completa (BU alvo) para resolver gd_name

    Schema esperado:
      TERRITORY_VEEVA, ACC NAME2, ACC HIERARCHY LEVEL, PARENT TERRITORY,
      ALLOCATION TYPE, NOME GD, SALES FORCE, BU, ISID, WEIN
    """
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]

    # Filtrar BU
    df_bu = df[df['BU'].astype(str).str.upper() == bu.upper()].copy()
    if len(df_bu) == 0:
        raise ValueError(f"Nenhuma linha encontrada para BU='{bu}'")

    # Padronizar ISID
    df_bu['ISID'] = df_bu['ISID'].astype(str).str.upper().str.strip()
    df_bu['ISID'] = df_bu['ISID'].replace({'NAN':None,'NONE':None,'':None})

    # Universo = REPs com ISID válido
    df_universo = df_bu[
        (df_bu['ACC HIERARCHY LEVEL']==HIERARCHY_FILTRO) &
        (df_bu['ISID'].notna())
    ].copy()

    # Normalizar campos
    df_universo['nome'] = df_universo['ACC NAME2'].astype(str).str.strip()
    df_universo['territorio'] = df_universo['TERRITORY_VEEVA'].astype(str).str.strip()
    df_universo['sales_force'] = df_universo['SALES FORCE'].astype(str).str.strip()

    # Excluir Sales Forces configuradas em SFS_EXCLUIDAS
    if SFS_EXCLUIDAS:
        antes = len(df_universo)
        df_universo = df_universo[~df_universo['sales_force'].isin(SFS_EXCLUIDAS)]
        excluidos = antes - len(df_universo)
        if excluidos > 0:
            print(f"    SFs excluídas ({', '.join(SFS_EXCLUIDAS)}): {excluidos} consultores removidos do universo")

    df_universo['gd_code'] = df_universo['PARENT TERRITORY'].astype(str).str.strip()
    df_universo['gd_name'] = df_universo['NOME GD'].astype(str).str.strip()
    df_universo['hierarchy'] = df_universo['ACC HIERARCHY LEVEL'].astype(str).str.strip()
    # Busca tolerante: tenta variações do nome da coluna WEIN ID
    _wein_candidates = ['ACC WEIN ID', 'WEIN ID', 'WIN ID', 'WEIN', 'WIN']
    _wein_col = next((c for c in _wein_candidates if c in df_universo.columns), None)
    if _wein_col:
        df_universo['win_id'] = pd.to_numeric(df_universo[_wein_col], errors='coerce')
    else:
        print(f'⚠️  AVISO: nenhuma coluna WEIN/WIN encontrada em estrutura.xlsx — win_id será NaN')
        print(f'   Colunas disponíveis: {list(df_universo.columns)}')
        df_universo['win_id'] = float('nan')

    # === CIDADE_SEDE / UF_SEDE (novas cols na estrutura) ===
    # Valor 'VERIFICAR' ou vazio → status 'em validação' (None)
    def _norm_sede(v):
        if pd.isna(v): return None
        s = str(v).strip()
        if s == '' or s == '0' or s.upper() in ('NAN','NONE','VERIFICAR'):
            return None
        return s

    def _norm_cidade(v):
        s = _norm_sede(v)
        if s is None: return None
        # Normalizar acentos para casar com derivar_uf e cidades_vis (uppercase ASCII)
        import unicodedata
        t = unicodedata.normalize('NFD', s).encode('ascii','ignore').decode('ascii')
        return t.upper().strip()

    # Mapa nome-completo → sigla (corrige cadastros com "PARA", "PARANA" etc.)
    _UF_NOME2SIGLA = {
        'ACRE':'AC','ALAGOAS':'AL','AMAPA':'AP','AMAZONAS':'AM','BAHIA':'BA',
        'CEARA':'CE','DISTRITO FEDERAL':'DF','ESPIRITO SANTO':'ES','GOIAS':'GO',
        'MARANHAO':'MA','MATO GROSSO':'MT','MATO GROSSO DO SUL':'MS','MINAS GERAIS':'MG',
        'PARA':'PA','PARAIBA':'PB','PARANA':'PR','PERNAMBUCO':'PE','PIAUI':'PI',
        'RIO DE JANEIRO':'RJ','RIO GRANDE DO NORTE':'RN','RIO GRANDE DO SUL':'RS',
        'RONDONIA':'RO','RORAIMA':'RR','SANTA CATARINA':'SC','SAO PAULO':'SP',
        'SERGIPE':'SE','TOCANTINS':'TO',
    }
    def _norm_uf(v):
        s = _norm_sede(v)
        if s is None: return None
        import unicodedata
        s = unicodedata.normalize('NFD', s).encode('ascii','ignore').decode('ascii').upper().strip()
        if len(s) == 2:
            return s
        return _UF_NOME2SIGLA.get(s, s)

    if 'CIDADE_SEDE' in df_universo.columns:
        df_universo['cidade_sede'] = df_universo['CIDADE_SEDE'].map(_norm_cidade)
        df_universo['cidade_sede_status'] = df_universo['CIDADE_SEDE'].map(
            lambda v: 'em_validacao' if _norm_sede(v) is None else 'ok')
    else:
        df_universo['cidade_sede'] = None
        df_universo['cidade_sede_status'] = 'em_validacao'

    if 'UF_SEDE' in df_universo.columns:
        df_universo['uf_sede_estrutura'] = df_universo['UF_SEDE'].map(_norm_uf)
    else:
        df_universo['uf_sede_estrutura'] = None

    # Resultado limpo
    universo = df_universo[[
        'ISID','nome','territorio','sales_force','gd_code','gd_name','win_id','hierarchy',
        'cidade_sede','cidade_sede_status','uf_sede_estrutura'
    ]].drop_duplicates(subset='ISID').reset_index(drop=True)

    return universo, df_bu


def carregar_universo():
    """Lê estrutura e produz dict ISID → metadados básicos."""
    univ, df_bu = ler_estrutura()
    print(f"[1] Estrutura: BU={BU_ALVO}, {len(df_bu)} pessoas totais, {len(univ)} REPs no universo")
    print(f"    GDs distintos: {univ['gd_name'].nunique()}")
    print(f"    Sales Forces: {univ['sales_force'].nunique()}")
    n_ok = (univ['cidade_sede_status']=='ok').sum()
    print(f"    Cidade sede preenchida: {n_ok}/{len(univ)}  ({len(univ)-n_ok} em validação)")
    return univ


# ============================================================================
# 2. AUSÊNCIAS — leitura, deduplicação reforçada, expansão diária
# ============================================================================
def ler_ausencias_bruto(path=None):
    """Lê o CSV original (separador ; / encoding latin-1)."""
    if path is None:
        path = IN('ausencias_de_campo_visao_geral.csv')
    df = pd.read_csv(path, sep=';', encoding='latin-1', dtype=str)
    df.columns = [c.replace('Território fora do horário comercial: ','').strip() for c in df.columns]

    # Renomear pra nomes curtos
    rename = {
        'ID do TOT': 'tot_id',
        'Nome do proprietário': 'nome',
        'Papel do proprietário': 'papel',
        'Motivo': 'motivo',
        'Submotivo': 'subtipo',
        'Data': 'data_inicio_str',
        'Data de Término': 'data_fim_str',
        'Duração': 'duracao',
        'Status': 'status',
        'Território fora do horário comercial: Criado por': 'criado_por',  # caso venha completo
        'Criado por': 'criado_por',
        'Alias do proprietário': 'isid',
        'KEY': 'key',
    }
    df = df.rename(columns=rename)

    # Limpar espaços
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].str.strip()

    # Filtrar só Confirmado (Planejado é projeção futura)
    bruto_n = len(df)
    df = df[df['status']=='Confirmado'].copy()
    print(f"[2.0] Ausências bruto: {bruto_n} linhas → {len(df)} confirmadas")

    # Remover feriado público (já descontado dos dias úteis)
    feriado_n = (df['subtipo']=='Feriado público').sum()
    df = df[df['subtipo']!='Feriado público'].copy()
    print(f"     {feriado_n} 'Feriado público' removidos (já no calendário)")

    # Datas
    df['data_inicio'] = pd.to_datetime(df['data_inicio_str'], format='%d/%m/%Y', errors='coerce')
    df['data_fim'] = pd.to_datetime(df['data_fim_str'], format='%d/%m/%Y', errors='coerce')

    # ISID padronizado
    df['isid'] = df['isid'].astype(str).str.upper().str.strip()

    return df


def deduplicar_ausencias(df):
    """
    Aplica regras R0, R1, R2, R3.
    R0 (NOVA): dedupe sem criado_por como chave (Integration User + consultor próprio criam mesmo lançamento)
    R1: duplicatas exatas remanescentes
    R2: Dia Inteiro + parcial no mesmo ISID/dia → mantém Dia Inteiro
    R3: subtipos diferentes mesmo ISID/dia/duração → mantém maior prioridade

    Retorna df deduplicado + df de auditoria (registros removidos).
    """
    n0 = len(df)
    audit = []  # [{'regra','tot_id','isid','data','duracao','subtipo','razao'}]

    # ============= R0 — sem criado_por como chave =============
    # chave: isid + data_inicio + data_fim + duracao + subtipo
    # Ordenação antes do dedup (alinhada ao dedup_2026.py original):
    #   1. Confirmado antes de Planejado
    #   2. Lançamento do consultor antes de Integration User
    # Assim, quando há conflito, mantemos o "melhor" registro.
    chave_r0 = ['isid','data_inicio','data_fim','duracao','subtipo']
    status_order = {'Confirmado': 0, 'Planejado': 1}
    df['_status_rank'] = df['status'].map(status_order).fillna(2)
    df['_is_integration'] = (df['criado_por'] == 'Integration User').astype(int)
    df = df.sort_values(by=chave_r0 + ['_status_rank','_is_integration','tot_id'])
    dups_r0 = df.duplicated(subset=chave_r0, keep='first')
    for _, row in df[dups_r0].iterrows():
        audit.append({
            'regra':'R0_integration_vs_propria','tot_id':row['tot_id'],'isid':row['isid'],
            'data':row['data_inicio'],'duracao':row['duracao'],'subtipo':row['subtipo'],
            'razao':'Mesma ausência lançada >1x (provável Integration User + consultor)'
        })
    df = df[~dups_r0].copy()
    n_r0 = n0 - len(df)
    print(f"[2.1] R0 (integration vs próprio): {n_r0} removidos → {len(df)} restantes")

    # ============= R1 — duplicatas exatas remanescentes =============
    # Já cobre. Pulamos.

    # ============= R2 — Dia Inteiro + parcial mesmo dia =============
    PARCIAIS = ['Durante a Manhã','Durante a Tarde','Início da Manhã',
                'Final da Manhã','Início da Tarde','Final da Tarde']
    df['_dia_inteiro'] = df['duracao']=='Dia Inteiro'
    df['_parcial'] = df['duracao'].isin(PARCIAIS)

    confl = (df.groupby(['isid','data_inicio'])
             .agg(tem_di=('_dia_inteiro','any'),
                  tem_par=('_parcial','any'))
             .reset_index())
    confl = confl[confl['tem_di'] & confl['tem_par']]
    pares = set(zip(confl['isid'], confl['data_inicio']))

    mask_r2 = df.apply(
        lambda r: (r['isid'],r['data_inicio']) in pares and r['duracao'] in PARCIAIS,
        axis=1
    )
    for _, row in df[mask_r2].iterrows():
        audit.append({
            'regra':'R2_dia_inteiro_vs_parcial','tot_id':row['tot_id'],'isid':row['isid'],
            'data':row['data_inicio'],'duracao':row['duracao'],'subtipo':row['subtipo'],
            'razao':'Parcial conflita com Dia Inteiro no mesmo dia'
        })
    df = df[~mask_r2].copy()
    n_r2 = sum(1 for a in audit if a['regra']=='R2_dia_inteiro_vs_parcial')
    print(f"[2.2] R2 (parcial vs dia inteiro): {n_r2} removidos → {len(df)} restantes")

    # ============= R3 — mesmo dia/duração, subtipos diferentes =============
    df['_prio'] = df['subtipo'].map(PRIORIDADE_SUBTIPO).fillna(0)
    # Para cada grupo (isid, data_inicio, duracao) com >1 subtipo, manter o de maior prioridade
    df = df.sort_values(['isid','data_inicio','duracao','_prio'], ascending=[True,True,True,False])
    chave_r3 = ['isid','data_inicio','duracao']
    dups_r3 = df.duplicated(subset=chave_r3, keep='first')
    for _, row in df[dups_r3].iterrows():
        audit.append({
            'regra':'R3_subtipo_conflitante','tot_id':row['tot_id'],'isid':row['isid'],
            'data':row['data_inicio'],'duracao':row['duracao'],'subtipo':row['subtipo'],
            'razao':'Mesmo ISID/data/duração com outro subtipo de maior prioridade'
        })
    df = df[~dups_r3].copy()
    n_r3 = sum(1 for a in audit if a['regra']=='R3_subtipo_conflitante')
    print(f"[2.3] R3 (subtipo conflitante): {n_r3} removidos → {len(df)} restantes")

    # Cleanup
    df = df.drop(columns=['_dia_inteiro','_parcial','_prio'], errors='ignore')
    df_audit = pd.DataFrame(audit) if audit else pd.DataFrame(columns=['regra','tot_id','isid','data','duracao','subtipo','razao'])
    print(f"[2.4] Total removido na dedup: {n0 - len(df)} ({100*(n0-len(df))/n0:.1f}%)")
    return df, df_audit


def expandir_ausencias_em_dias(df, isids_universo):
    """
    Expande cada registro em N linhas (uma por dia útil).
    Aplica equivalência de duração → fração de dia.
    Categoriza cada linha.
    Cap em 1.0 por ISID/dia (subcategoria ≤ total).
    """
    # Filtrar pelo universo (só ISIDs analisados)
    df = df[df['isid'].isin(isids_universo)].copy()
    print(f"[2.5] Após filtro pelo universo ({len(isids_universo)} ISIDs): {len(df)} registros")

    registros = []
    for _, row in df.iterrows():
        isid = row['isid']
        subtipo = row['subtipo']
        dur = row['duracao']
        dt_ini = row['data_inicio']
        dt_fim = row['data_fim']
        tot_id = row['tot_id']
        if pd.isna(dt_ini):
            continue
        categoria = SUBTIPOS.get(subtipo, CAT_OUTROS)

        # Expansão
        dias_a_marcar = []
        if dur == 'Ausência Longa' and pd.notna(dt_fim):
            for dia in pd.date_range(start=dt_ini, end=dt_fim, freq='D'):
                if eh_dia_util(dia):
                    dias_a_marcar.append((dia, 1.0, f"Ausência Longa ({dt_ini.strftime('%d/%m')}–{dt_fim.strftime('%d/%m')})"))
        elif dur in ['2 Dias','3 Dias','4 Dias','5 Dias']:
            n_dias = int(dur.split()[0])
            contados = 0
            dia_atual = dt_ini
            while contados < n_dias:
                if eh_dia_util(dia_atual):
                    dias_a_marcar.append((dia_atual, 1.0, f"{dur} (início {dt_ini.strftime('%d/%m')})"))
                    contados += 1
                dia_atual += pd.Timedelta(days=1)
        elif dur in EQUIV_DUR:
            if eh_dia_util(dt_ini):
                dias_a_marcar.append((dt_ini, EQUIV_DUR[dur], dur))
        else:
            if eh_dia_util(dt_ini):
                dias_a_marcar.append((dt_ini, 1.0, dur))

        for dia, fr, dur_label in dias_a_marcar:
            registros.append({
                'tot_id': tot_id,
                'isid': isid,
                'data': dia.date() if isinstance(dia, pd.Timestamp) else dia,
                'ano': (dia.year if hasattr(dia,'year') else None),
                'mes': (dia.month if hasattr(dia,'month') else None),
                'subtipo': subtipo,
                'categoria': categoria,
                'duracao_label': dur_label,
                'fr_total': fr,
                'fr_viagem': fr if categoria == CAT_VIAGEM else 0.0,
                'fr_reuniao': fr if categoria == CAT_REUNIAO else 0.0,
                'fr_congresso': fr if categoria == CAT_CONGRESSO else 0.0,
                'fr_treinamento': fr if categoria == CAT_TREINAMENTO else 0.0,
                'fr_gestao': fr if categoria == CAT_GESTAO else 0.0,
                'fr_pessoal': fr if categoria == CAT_PESSOAL else 0.0,
                'fr_outros': fr if categoria == CAT_OUTROS else 0.0,
            })

    df_exp = pd.DataFrame(registros)
    print(f"[2.6] Registros expandidos em dias: {len(df_exp)}")

    # Agregar por ISID/dia com cap 1.0
    fr_cols = ['fr_total','fr_viagem','fr_reuniao','fr_congresso',
               'fr_treinamento','fr_gestao','fr_pessoal','fr_outros']
    df_dia = (df_exp.groupby(['isid','data','ano','mes'], as_index=False)[fr_cols].sum())

    # Cap geral em 1.0
    for c in fr_cols:
        df_dia[c] = df_dia[c].clip(upper=1.0)
    # Subcategorias ≤ total
    for c in fr_cols[1:]:
        df_dia[c] = np.minimum(df_dia[c], df_dia['fr_total'])

    return df_exp, df_dia


# ============================================================================
# 3. LEITURA DAS VISITAS (3 CSVs separados, um por ano)
# ============================================================================
def ler_visitas(paths=None):
    """
    Lê e concatena relatorio_visitas_24/25/26.csv.
    Filtra: F2F + Submitted_vod + Person Account.
    Retorna df com colunas normalizadas.
    """
    if paths is None:
        paths = [IN('relatorio_visitas_24.csv'),
                 IN('relatorio_visitas_25.csv'),
                 IN('relatorio_visitas_26.csv')]

    dfs = []
    for p in paths:
        if not os.path.exists(p):
            print(f"    AVISO: {p} não encontrado, pulando")
            continue
        df = pd.read_csv(p, sep=';', encoding='utf-8', dtype=str, low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)
    n0 = len(df)

    # Filtros
    df['CALL TYPE'] = df['CALL TYPE'].str.strip()
    df['CALL SUB TYPE'] = df['CALL SUB TYPE'].astype(str).str.strip()
    df = df[df['CALL STATUS']=='Submitted_vod'].copy()
    df = df[df['CALL SUB TYPE']=='F2F'].copy()  # só presencial
    df = df[df['ACC TYPE']=='Person Account'].copy()
    print(f"[3.0] Visitas: bruto {n0} → válidas F2F Submitted {len(df)}")

    # Normalizar colunas relevantes
    df['data'] = pd.to_datetime(df['CALL DATE'], format='%d/%m/%Y', errors='coerce')
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month
    df['isid_win'] = pd.to_numeric(df['USR WIN ID'], errors='coerce')
    df['mdm'] = df['ACC MDM ID'].astype(str).str.strip()
    df['acc_name'] = df['ACC NAME'].astype(str).str.strip()
    df['acc_specialty'] = df['ACC PRIMARY SPECIALTY'].astype(str).str.strip()
    df['call_city'] = df['CALL CITY'].astype(str).str.strip().str.upper()
    df['acc_city'] = df['ACCOUNT CITY'].astype(str).str.strip().str.upper()
    df['call_territory'] = df['CALL TERRITORY'].astype(str).str.strip()
    df['sales_team'] = df['USR SALES TEAM (C)'].astype(str).str.strip()
    return df


def ler_medicos_1030(path=None):
    """
    Lê o relatorio_1030.csv — fonte oficial de Nome do médico + CRM (ACC MEDICAL ID).

    Schema esperado:
      ACC MDM ID | ACC FIRST NAME | ACC LAST NAME | ACC INDIVIDUAL TYPE |
      ACC PRIMARY SPECIALTY | ACC SECONDARY SPECIALTY | ACC MEDICAL ID

    Retorna dict: { mdm_id_str: {nome, crm, tipo, especialidade} }
    Nome é formatado em Proper Case (Title case), concatenando First + Last.
    Ex: 'CRISTINA' + 'CARVALHO PÓVOA' → 'Cristina Carvalho Póvoa'

    Se o arquivo não existir, retorna {} (graceful — payload continua sem nome/CRM).
    """
    if path is None:
        path = IN('relatorio_1030.csv')
    if not os.path.exists(path):
        print(f"    AVISO: {path} não encontrado, payload ficará sem nome/CRM dos médicos")
        return {}

    # encoding='utf-8-sig' remove o BOM no início do arquivo
    df = pd.read_csv(path, sep=';', encoding='utf-8-sig', dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    # Validação de colunas esperadas
    cols_req = ['ACC MDM ID', 'ACC FIRST NAME', 'ACC LAST NAME', 'ACC MEDICAL ID']
    faltando = [c for c in cols_req if c not in df.columns]
    if faltando:
        print(f"    AVISO: relatorio_1030.csv sem colunas {faltando} — payload sem dados desses campos")
        return {}

    # Limpeza e concatenação First + " " + Last → Proper Case
    df['ACC FIRST NAME'] = df['ACC FIRST NAME'].fillna('').astype(str).str.strip()
    df['ACC LAST NAME']  = df['ACC LAST NAME'].fillna('').astype(str).str.strip()
    df['nome_completo'] = (df['ACC FIRST NAME'] + ' ' + df['ACC LAST NAME']).str.strip().str.title()
    # str.title() converte "DE OLIVEIRA" → "De Oliveira" (Proper Case). É o que a Raissa pediu.

    # CRM (ACC MEDICAL ID), tipo e especialidade
    df['crm'] = df['ACC MEDICAL ID'].fillna('').astype(str).str.strip()
    df['tipo'] = df.get('ACC INDIVIDUAL TYPE', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
    df['especialidade'] = df.get('ACC PRIMARY SPECIALTY', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()

    df['mdm'] = df['ACC MDM ID'].astype(str).str.strip()
    # Remove duplicatas de MDM (se houver) — fica com a primeira
    df = df.drop_duplicates(subset='mdm', keep='first')

    out = {}
    for _, row in df.iterrows():
        mdm = row['mdm']
        # Tratar NaN/float (str(NaN) = 'nan', mas se vier float puro precisa converter)
        if pd.isna(mdm):
            continue
        mdm = str(mdm).strip()
        if not mdm or mdm.lower() == 'nan':
            continue
        out[mdm] = {
            'nome': row['nome_completo'] or '',
            'crm': row['crm'] or '',
            'tipo': row['tipo'] or '',
            'especialidade': row['especialidade'] or '',
        }
    print(f"[3.5] Médicos lidos do relatorio_1030.csv: {len(out):,} MDMs únicos")
    com_crm = sum(1 for v in out.values() if v['crm'])
    com_nome = sum(1 for v in out.values() if v['nome'])
    print(f"      Com CRM preenchido: {com_crm:,} · Com nome: {com_nome:,}")
    return out


def visitas_com_isid(df_visitas, universo):
    """
    Faz join com universo via win_id → ISID.
    Filtra visitas só do universo de análise (REPs Oncologia).
    Filtra fantasmas futuros (data > HOJE).

    Se INCLUIR_MES_PARCIAL=True, mantém visitas do mês corrente parcial — útil pra
    séries temporais e janelas curtas. Métricas MAT 12m continuam baseadas só em
    meses fechados (filtro por JANELA_INI..JANELA_FIM em calcular_metricas).
    """
    df = df_visitas.copy()
    # Join via win_id
    win_to_isid = dict(zip(universo['win_id'].astype(float), universo['ISID']))
    df['ISID'] = df['isid_win'].map(win_to_isid)
    n_match = df['ISID'].notna().sum()
    print(f"[3.1] Visitas com ISID no universo: {n_match}/{len(df)} ({100*n_match/len(df):.1f}%)")
    df = df[df['ISID'].notna()].copy()

    # Cutoff:
    #   - Se INCLUIR_MES_PARCIAL=True: corta em HOJE (fantasmas futuros) — preserva maio parcial
    #   - Se False:                    corta no fim do MES_FECHADO (comportamento antigo)
    if INCLUIR_MES_PARCIAL:
        cutoff = pd.Timestamp(HOJE)
        rotulo = f"hoje ({HOJE}) — incluindo mês parcial {MES_PARCIAL.strftime('%Y-%m')}"
    else:
        cutoff = pd.Timestamp(MES_FECHADO.year, MES_FECHADO.month, 1) + pd.offsets.MonthEnd(0)
        rotulo = f"{cutoff.date()} (mês fechado)"
    n_pre = len(df)
    df = df[df['data'] <= cutoff].copy()
    print(f"[3.2] Visitas após corte em {rotulo}: {len(df)} ({n_pre-len(df)} removidas como projeção/fantasma)")

    # Reportar quantas são do mês parcial
    if INCLUIR_MES_PARCIAL:
        ym_parcial = f"{MES_PARCIAL.year:04d}-{MES_PARCIAL.month:02d}"
        n_parcial = (df['data'].dt.strftime('%Y-%m') == ym_parcial).sum()
        if n_parcial > 0:
            dias_decorridos = HOJE.day
            print(f"[3.3] Mês parcial {ym_parcial}: {n_parcial} visitas (dia {dias_decorridos} do mês)")

    return df


# ============================================================================
# 4. MÉTRICAS POR CONSULTOR (MAT + mensal)
# ============================================================================
def calcular_metricas_consultor(universo, df_visitas, df_ausencia_dia,
                                  trocas_csv=None, trocas_gd_csv=None):
    """
    Para cada consultor, calcula bloco completo de KPIs.
    Janelas usadas:
      - SNAPSHOT: foto do mês corrente fechado (painel atual)
      - MAT 12m: janela rolling 12 meses fechados (JANELA_INI a JANELA_FIM)
      - MES_FECHADO: último mês fechado isolado

    PARÂMETROS ADICIONAIS:
      trocas_csv:    dict retornado por ler_excecoes_trocas_sf() — trocas de SF.
      trocas_gd_csv: dict retornado por ler_excecoes_trocas_gd() — trocas de GD. (Onda v8)

    Para consultores com 'troca_real' em SF e/ou GD, vis_mat e aus_mat serão
    RECORTADOS a partir da TROCA MAIS RECENTE (decisão de produto).
    """
    janela_ini_ts = pd.Timestamp(JANELA_INI)
    # Fim da janela = último dia do MES_FECHADO
    if MES_FECHADO.month == 12:
        janela_fim_ts = pd.Timestamp(MES_FECHADO.year, 12, 31)
    else:
        janela_fim_ts = pd.Timestamp(MES_FECHADO.year, MES_FECHADO.month+1, 1) - pd.Timedelta(days=1)

    # === Onda v7+v8: Mapa de cortes combinado (SF e/ou GD) ===
    corte_combinado = calcular_corte_combinado(
        trocas_csv or {'trocas_reais': {}},
        trocas_gd_csv or {'trocas_reais': {}},
    )
    cortes_por_isid = {}   # ISID → pd.Timestamp (data_inicio_efetiva)
    if corte_combinado:
        for _, row in universo.iterrows():
            wid = row.get('win_id')
            isid = row.get('ISID')
            if pd.isna(wid) or not isid:
                continue
            wid_int = int(wid)
            if wid_int in corte_combinado:
                ano_q, mes_q = corte_combinado[wid_int]['mes_quebra']
                data_corte = pd.Timestamp(ano_q, mes_q, 1)
                cortes_por_isid[isid] = data_corte

    if cortes_por_isid:
        cnt_origem = {'sf': 0, 'gd': 0, 'sf_e_gd_pega_sf': 0, 'sf_e_gd_pega_gd': 0}
        for _, row in universo.iterrows():
            wid = row.get('win_id')
            if pd.isna(wid):
                continue
            wid_int = int(wid)
            if wid_int in corte_combinado:
                origem = corte_combinado[wid_int]['origem']
                cnt_origem[origem] = cnt_origem.get(origem, 0) + 1
        print(f"    [Onda v7+v8] Cortes aplicados: {len(cortes_por_isid)} consultores")
        print(f"      Por SF: {cnt_origem['sf']} | Por GD: {cnt_origem['gd']} | "
              f"Ambos (pegou SF): {cnt_origem['sf_e_gd_pega_sf']} | "
              f"Ambos (pegou GD): {cnt_origem['sf_e_gd_pega_gd']}")

    # === Visitas dentro da janela MAT ===
    vis_mat = df_visitas[(df_visitas['data'] >= janela_ini_ts) &
                         (df_visitas['data'] <= janela_fim_ts)].copy()

    # === Ausências dentro da janela MAT ===
    aus_mat = df_ausencia_dia[
        (pd.to_datetime(df_ausencia_dia['data']) >= janela_ini_ts) &
        (pd.to_datetime(df_ausencia_dia['data']) <= janela_fim_ts)
    ].copy()

    # === Dias úteis na janela MAT (12 meses) ===
    uteis_por_mes = {}
    cursor = JANELA_INI
    while cursor <= JANELA_FIM:
        uteis_por_mes[(cursor.year, cursor.month)] = dias_uteis_mes(cursor.year, cursor.month)
        cursor = date(cursor.year + (cursor.month==12), (cursor.month%12)+1, 1)
    uteis_12m_total = sum(uteis_por_mes.values())

    # === Onda v8 bugfix: limite superior para recortes pós-janela ===
    # Quando o corte (troca de SF/GD) é APÓS janela_fim_ts (ex: troca em mai/26
    # com MES_FECHADO=abr/26), filtrar vis_mat (que termina em abr/26) zera tudo.
    # Solução: para esses casos, ler visitas do df_visitas original até hoje.
    hoje_ts = pd.Timestamp(date.today())

    # === DENOMINADOR COMUM (calendário, igual para todos os consultores) ===
    # Calculado UMA VEZ fora do loop. Vai em DATA.meta no payload.
    # O front usa esse valor como denominador nos gráficos de ausência por arquétipo,
    # garantindo que Local, Viagem Interna e Interestadual sejam comparáveis.

    # Último quarter fechado (Q anterior ao corrente)
    _q_c_num = (MES_FECHADO.month - 1) // 3 + 1
    _q_c_ano = MES_FECHADO.year
    _q_p_num = _q_c_num - 1
    _q_p_ano = _q_c_ano
    if _q_p_num <= 0:
        _q_p_num = 4
        _q_p_ano -= 1
    _q_p_mes_ini = (_q_p_num - 1) * 3 + 1

    # Último mês fechado: usar MES_FECHADO diretamente, sem avançar mês via %12+1.
    _cutoff_1m_comum = pd.Timestamp(MES_FECHADO.year, MES_FECHADO.month, 1)

    _dias_uteis_3m_comum = sum(
        dias_uteis_mes(_q_p_ano, _q_p_mes_ini + i)
        for i in range(3)
    )
    _dias_uteis_1m_comum = uteis_por_mes.get(
        (_cutoff_1m_comum.year, _cutoff_1m_comum.month), 0)
    _dias_uteis_parcial_comum = dias_uteis_mes(MES_PARCIAL.year, MES_PARCIAL.month) if INCLUIR_MES_PARCIAL else 0
    _dias_decorridos_parcial_comum = sum(
        1 for d in pd.date_range(
            pd.Timestamp(MES_PARCIAL.year, MES_PARCIAL.month, 1),
            pd.Timestamp(date.today())
        ) if eh_dia_util(d)
    ) if INCLUIR_MES_PARCIAL else 0


    UTEIS_COMUM = {
        'uteis_mes_comum_mat':       round(float(uteis_12m_total) / 12, 2),
        'uteis_total_comum_mat':     float(uteis_12m_total),
        'uteis_mes_comum_3m':        round(float(_dias_uteis_3m_comum) / 3, 2),
        'uteis_total_comum_3m':      float(_dias_uteis_3m_comum),
        'uteis_mes_comum_1m':        round(float(_dias_uteis_1m_comum), 2),
        'uteis_total_comum_1m':      float(_dias_uteis_1m_comum),
        'uteis_mes_comum_parcial':   round(float(_dias_decorridos_parcial_comum), 2),
        'uteis_total_comum_parcial': float(_dias_uteis_parcial_comum),
        'uteis_decorridos_comum_parcial': float(_dias_decorridos_parcial_comum),
    }
    print(f"    [DENOMINADOR COMUM] MAT={UTEIS_COMUM['uteis_mes_comum_mat']}d/mês · "
          f"3m={UTEIS_COMUM['uteis_mes_comum_3m']}d/mês · "
          f"1m={UTEIS_COMUM['uteis_mes_comum_1m']}d · "
          f"parcial={UTEIS_COMUM['uteis_mes_comum_parcial']}d decorridos")

    rows = []
    for _, p in universo.iterrows():
        isid = p['ISID']

        # === Onda v7+v8: definir janela individual quando há corte ===
        if isid in cortes_por_isid:
            _corte = cortes_por_isid[isid]
            if _corte > janela_fim_ts:
                # Corte está APÓS o último mês fechado.
                # Janela individual = [corte, hoje] — usa visitas do mês parcial.
                vis_p = df_visitas[
                    (df_visitas['ISID'] == isid) &
                    (df_visitas['data'] >= _corte) &
                    (df_visitas['data'] <= hoje_ts)
                ].copy()
                aus_p = df_ausencia_dia[
                    (df_ausencia_dia['isid'] == isid) &
                    (pd.to_datetime(df_ausencia_dia['data']) >= _corte) &
                    (pd.to_datetime(df_ausencia_dia['data']) <= hoje_ts)
                ].copy()
            else:
                # Corte dentro da janela MAT normal — recortar como antes.
                vis_p = vis_mat[vis_mat['ISID'] == isid]
                aus_p = aus_mat[aus_mat['isid'] == isid]
                vis_p = vis_p[vis_p['data'] >= _corte]
                aus_p = aus_p[pd.to_datetime(aus_p['data']) >= _corte]
        else:
            # Sem corte — janela MAT padrão
            vis_p = vis_mat[vis_mat['ISID'] == isid]
            aus_p = aus_mat[aus_mat['isid'] == isid]

        n_visitas = len(vis_p)
        n_medicos_unicos = vis_p['mdm'].nunique()
        n_dias_ativos = vis_p['data'].dt.normalize().nunique()

        # === Dias úteis EFETIVOS da janela deste consultor ===
        # Para a maioria: uteis_12m_total (janela MAT completa).
        # Para consultores com corte (troca de SF/GD): apenas meses a partir do corte.
        if isid in cortes_por_isid:
            _corte = cortes_por_isid[isid]
            # Calcular dias úteis apenas dos meses a partir do corte
            uteis_janela_total = 0
            cursor_uteis = date(_corte.year, _corte.month, 1)
            # Limite: se corte pós-janela, vai até hoje; senão, até fim da janela MAT
            if _corte > janela_fim_ts:
                limite_uteis = date(hoje_ts.year, hoje_ts.month, 1)
            else:
                limite_uteis = JANELA_FIM
            while cursor_uteis <= limite_uteis:
                uteis_janela_total += dias_uteis_mes(cursor_uteis.year, cursor_uteis.month)
                if cursor_uteis.month == 12:
                    cursor_uteis = date(cursor_uteis.year + 1, 1, 1)
                else:
                    cursor_uteis = date(cursor_uteis.year, cursor_uteis.month + 1, 1)
        else:
            uteis_janela_total = uteis_12m_total

        # Ausência MAT: total = soma das categorias exibidas
        viagem_12m = aus_p['fr_viagem'].sum()
        reuniao_12m = aus_p['fr_reuniao'].sum()
        congresso_12m = aus_p['fr_congresso'].sum()
        treinamento_12m = aus_p['fr_treinamento'].sum()
        gestao_12m = aus_p['fr_gestao'].sum()
        pessoal_12m = aus_p['fr_pessoal'].sum()
        ausencia_12m = (
            viagem_12m + reuniao_12m + congresso_12m +
            treinamento_12m + gestao_12m + pessoal_12m
        )
        # Dias trabalhados na janela efetiva
        trab_12m = max(0, uteis_janela_total - ausencia_12m)

        # Métrica-chave: visitas/dia = visitas / dias_trabalhados
        vis_dia_media = (n_visitas / trab_12m) if trab_12m > 0 else 0.0

        # Médicos únicos por mês — DUAS versões com semânticas diferentes:
        #   - medicos_unicos_mes_painel: média mensal de médicos únicos visitados (painel mensal real)
        #   - medicos_unicos_mes_taxa:   medicos_12m / meses_ativos (taxa de incidência — compat antiga)
        vis_p_aux = vis_p.copy()
        vis_p_aux['ym'] = vis_p_aux['data'].dt.to_period('M').astype(str)
        unicos_por_mes = vis_p_aux.groupby('ym')['mdm'].nunique()
        medicos_unicos_mes_painel = float(unicos_por_mes.mean()) if len(unicos_por_mes) else 0.0
        meses_ativos_efetivo = len(unicos_por_mes)
        medicos_unicos_mes_taxa = (n_medicos_unicos / meses_ativos_efetivo) if meses_ativos_efetivo > 0 else 0.0
        # Freq do médico = visitas/médico no MAT (= número de vezes que cada médico foi visitado em 12 meses)
        freq_medico_mes = (n_visitas / n_medicos_unicos / max(1, meses_ativos_efetivo)) if n_medicos_unicos > 0 else 0.0
        # Variável principal usada nas tabelas — painel mensal real (NOVA)
        medicos_unicos_mes = medicos_unicos_mes_painel

        # vis_dia também medida por dia ativo (referência)
        vis_p_dia = vis_p.groupby(vis_p['data'].dt.date).size()
        vis_dia_mediana = float(vis_p_dia.median()) if len(vis_p_dia) else 0.0
        vis_dia_max = float(vis_p_dia.max()) if len(vis_p_dia) else 0.0
        cv_vis_dia = (float(vis_p_dia.std()) / float(vis_p_dia.mean()) * 100) \
                     if len(vis_p_dia) and vis_p_dia.mean() else 0.0

        # Médias por mês — usa janela efetiva (12 meses normal, ou n_meses desde o corte)
        if isid in cortes_por_isid:
            _corte = cortes_por_isid[isid]
            if _corte > janela_fim_ts:
                n_meses_janela = max(1, (hoje_ts.year - _corte.year) * 12 + (hoje_ts.month - _corte.month) + 1)
            else:
                # Corte dentro do MAT: contar meses do corte até JANELA_FIM
                n_meses_janela = max(1, (JANELA_FIM.year - _corte.year) * 12 + (JANELA_FIM.month - _corte.month) + 1)
        else:
            n_meses_janela = 12
        uteis_mes_med = uteis_janela_total / n_meses_janela
        ausencia_mes_med = ausencia_12m / n_meses_janela
        viagem_mes_med = viagem_12m / n_meses_janela
        reuniao_mes_med = reuniao_12m / n_meses_janela
        congresso_mes_med = congresso_12m / n_meses_janela
        treinamento_mes_med = treinamento_12m / n_meses_janela
        gestao_mes_med = gestao_12m / n_meses_janela
        pessoal_mes_med = pessoal_12m / n_meses_janela
        trab_mes_med = trab_12m / n_meses_janela

        pct_ausencia = (ausencia_12m / uteis_janela_total * 100) if uteis_janela_total else 0.0
        pct_trab = 100 - pct_ausencia

        # === SNAPSHOT (último mês fechado, ou mês corrente quando corte pós-janela) ===
        # Para a maioria, painel_mes_fechado vem do MES_FECHADO (abr/26).
        # Onda v8 bugfix: para consultores com corte APÓS janela_fim, usar o
        # mês corrente (parcial) — senão snapshot fica zerado porque vis_p
        # só tem dados a partir do corte (que é DEPOIS do mês fechado).
        if isid in cortes_por_isid and cortes_por_isid[isid] > janela_fim_ts:
            ym_fechado = f"{hoje_ts.year:04d}-{hoje_ts.month:02d}"
        else:
            ym_fechado = f"{MES_FECHADO.year:04d}-{MES_FECHADO.month:02d}"
        vis_snap = vis_p_aux[vis_p_aux['ym']==ym_fechado]
        painel_proxy_snap = vis_snap['mdm'].nunique()

        # === Painel proxy (90 dias) ===
        # Normal: 90 dias antes de janela_fim_ts (jan/26 a abr/26)
        # Onda v8 bugfix: para consultores com corte APÓS janela_fim, usar
        # 90 dias antes de HOJE (assim pega visitas do mês parcial).
        if isid in cortes_por_isid and cortes_por_isid[isid] > janela_fim_ts:
            cutoff_90 = hoje_ts - pd.Timedelta(days=90)
        else:
            cutoff_90 = janela_fim_ts - pd.Timedelta(days=90)
        vis_90d = vis_p[vis_p['data'] >= cutoff_90]
        painel_proxy_90d = vis_90d['mdm'].nunique()
        # Lista de MDMs do proxy 90d — usada como fallback quando não há painel oficial.
        # Sem isso, mdms_painel fica [] e 100% das visitas viram "fora do painel".
        mdms_proxy_90d = sorted(set(str(m) for m in vis_90d['mdm'].dropna()))

        # === Geografia ===
        cidades_uniq = set(vis_p['call_city'].dropna()) - {'NAN','',' '}
        # UF: heurística (a planilha não tem UF explícito, derivar do CALL ADDRESS ou usar a partir do ACCOUNT)
        # Por ora deixa null e usa só cidades
        n_cidades = len(cidades_uniq)
        # Lista pequena pra debug
        cidades_top = vis_p['call_city'].value_counts().head(5).to_dict()

        # === Tendência (slope vis/dia em 12 meses) ===
        if len(unicos_por_mes) >= 3:
            ymeses_sorted = sorted(set(vis_p_aux['ym']))
            vis_mes = vis_p_aux.groupby('ym').size().reindex(ymeses_sorted, fill_value=0)
            # vis/dia por mês = vis_mes / (uteis_mes - ausencia_mes)
            vd_serie = []
            for ym in ymeses_sorted:
                ano_, mes_ = map(int, ym.split('-'))
                uteis_mes_ym = uteis_por_mes.get((ano_, mes_), 0)
                aus_mes_ym = aus_p[(aus_p['ano']==ano_)&(aus_p['mes']==mes_)]['fr_total'].sum()
                trab_mes_ym = max(0, uteis_mes_ym - aus_mes_ym)
                vd = vis_mes[ym] / trab_mes_ym if trab_mes_ym > 0 else 0
                vd_serie.append(vd)
            x = np.arange(len(vd_serie))
            if len(vd_serie) >= 3 and np.std(vd_serie) > 0:
                slope = float(np.polyfit(x, vd_serie, 1)[0])
            else:
                slope = 0.0
            if abs(slope) < 0.02:
                tend = 'Estável'
            elif slope < 0:
                tend = 'Piorando'
            else:
                tend = 'Melhorando'

            # === SLOPE da janela "Movimento do time" — adaptativo ===
            # Idealmente usa 6 meses fechados. Mas se só temos 3-5 meses (carregamento parcial
            # de dados históricos), usa o que houver e marca o size na meta.
            # Mínimo: 3 pontos (regressão linear precisa de pelo menos isso).
            n_window = min(6, len(vd_serie))
            if n_window >= 3:
                vdN = vd_serie[-n_window:]
                vd3 = vd_serie[-3:]
                xN = np.arange(n_window)
                if np.std(vdN) > 0:
                    slope_6m = float(np.polyfit(xN, vdN, 1)[0])
                else:
                    slope_6m = 0.0
                if abs(slope_6m) < 0.02: tend_6m = 'Estável'
                elif slope_6m < 0:       tend_6m = 'Piorando'
                else:                    tend_6m = 'Melhorando'
                vd_3m_media = float(np.mean(vd3)) if vd3 else 0.0
                vd_6m_media = float(np.mean(vdN)) if vdN else 0.0
                vd_6m_serie = [round(v, 2) for v in vdN]
                slope_window_n = n_window  # quantos meses usados (3-6)
                # Onda v3 — Série de VISITAS/MÊS (não vis/dia) para cálculo do ICV.
                # Usa a mesma janela do vd_6m_serie pra manter consistência temporal.
                # vis_mes já é uma Series indexada por ym → pegar os últimos n_window valores
                # respeitando a ordem cronológica (ymeses_sorted).
                ymesesN = ymeses_sorted[-n_window:]
                visitas_mes_serie = [int(vis_mes[ym]) for ym in ymesesN]
            else:
                slope_6m = 0.0
                tend_6m = 'Sem dados'
                vd_3m_media = vd_6m_media = 0.0
                vd_6m_serie = []
                slope_window_n = 0
                visitas_mes_serie = []
        else:
            slope = 0.0
            tend = 'Sem dados'
            slope_6m = 0.0
            tend_6m = 'Sem dados'
            vd_3m_media = vd_6m_media = 0.0
            vd_6m_serie = []
            slope_window_n = 0
            visitas_mes_serie = []

        # === Listas de MDMs por janela ===
        mdms_visitados_mat = sorted(set(str(m) for m in vis_p['mdm'].dropna()))

        # Último Quarter Fechado (Q anterior ao corrente)
        _q_curr_num = (MES_FECHADO.month - 1) // 3 + 1
        _q_curr_ano = MES_FECHADO.year
        _q_prev_num = _q_curr_num - 1
        _q_prev_ano = _q_curr_ano
        if _q_prev_num <= 0:
            _q_prev_num = 4
            _q_prev_ano -= 1
        _q_prev_mes_ini = (_q_prev_num - 1) * 3 + 1
        _q_prev_ini = pd.Timestamp(_q_prev_ano, _q_prev_mes_ini, 1)
        _q_prev_fim = pd.Timestamp(_q_prev_ano, _q_prev_mes_ini + 2, 1) + pd.offsets.MonthEnd(0)

        vis_3m = vis_p[(vis_p['data'] >= _q_prev_ini) & (vis_p['data'] <= _q_prev_fim)]

        # Último mês fechado: filtrar exatamente o mês MES_FECHADO.
        cutoff_1m = pd.Timestamp(MES_FECHADO.year, MES_FECHADO.month, 1)
        vis_1m = vis_p[
            (vis_p['data'].dt.year == MES_FECHADO.year) &
            (vis_p['data'].dt.month == MES_FECHADO.month)
        ]

        mdms_visitados_3m = sorted(set(str(m) for m in vis_3m['mdm'].dropna()))
        mdms_visitados_1m = sorted(set(str(m) for m in vis_1m['mdm'].dropna()))
        n_visitas_3m = int(len(vis_3m))
        n_visitas_1m = int(len(vis_1m))

        # Dias úteis por janela
        dias_uteis_3m = sum(
            uteis_por_mes.get((_q_prev_ano, _q_prev_mes_ini + i), 0)
            for i in range(3)
        )
        dias_uteis_1m = uteis_por_mes.get((MES_FECHADO.year, MES_FECHADO.month), 0)
        # AUSÊNCIA REAL por janela (não aproximação) — agrega aus_p pelos dias dentro da janela

        if len(aus_p):
            aus_p_dt = pd.to_datetime(aus_p['data'])
            mask_3m = (aus_p_dt >= _q_prev_ini) & (aus_p_dt <= _q_prev_fim)
            mask_1m = (
                (aus_p_dt.dt.year == MES_FECHADO.year) &
                (aus_p_dt.dt.month == MES_FECHADO.month)
            )

            # Ampliação (item Ausências — filtros de período): somar cada categoria por janela
            viagem_3m       = aus_p[mask_3m]['fr_viagem'].sum()
            reuniao_3m      = aus_p[mask_3m]['fr_reuniao'].sum()
            congresso_3m    = aus_p[mask_3m]['fr_congresso'].sum()
            treinamento_3m  = aus_p[mask_3m]['fr_treinamento'].sum()
            gestao_3m       = aus_p[mask_3m]['fr_gestao'].sum()
            pessoal_3m      = aus_p[mask_3m]['fr_pessoal'].sum()
            aus_3m_real     = viagem_3m + reuniao_3m + congresso_3m + treinamento_3m + gestao_3m + pessoal_3m

            viagem_1m       = aus_p[mask_1m]['fr_viagem'].sum()
            reuniao_1m      = aus_p[mask_1m]['fr_reuniao'].sum()
            congresso_1m    = aus_p[mask_1m]['fr_congresso'].sum()
            treinamento_1m  = aus_p[mask_1m]['fr_treinamento'].sum()
            gestao_1m       = aus_p[mask_1m]['fr_gestao'].sum()
            pessoal_1m      = aus_p[mask_1m]['fr_pessoal'].sum()
            aus_1m_real     = viagem_1m + reuniao_1m + congresso_1m + treinamento_1m + gestao_1m + pessoal_1m
        else:
            aus_3m_real = aus_1m_real = 0
            viagem_3m = reuniao_3m = congresso_3m = treinamento_3m = gestao_3m = pessoal_3m = 0
            viagem_1m = reuniao_1m = congresso_1m = treinamento_1m = gestao_1m = pessoal_1m = 0

        pct_aus_3m = round(100*aus_3m_real/dias_uteis_3m, 2) if dias_uteis_3m > 0 else 0
        pct_aus_1m = round(100*aus_1m_real/dias_uteis_1m, 2) if dias_uteis_1m > 0 else 0
        trab_3m = max(1, dias_uteis_3m - aus_3m_real)
        trab_1m = max(1, dias_uteis_1m - aus_1m_real)
        vis_dia_3m = (n_visitas_3m / trab_3m) if trab_3m > 0 else 0
        vis_dia_1m = (n_visitas_1m / trab_1m) if trab_1m > 0 else 0

        # Médias mensais por janela (divide pelo nº de meses da janela)
        ausencia_mes_3m      = aus_3m_real / 3
        viagem_mes_3m        = viagem_3m / 3
        reunioes_mes_3m      = reuniao_3m / 3
        congressos_mes_3m    = congresso_3m / 3
        treinamento_mes_3m   = treinamento_3m / 3
        gestao_mes_3m        = gestao_3m / 3
        pessoais_mes_3m      = pessoal_3m / 3
        trabalhados_mes_3m   = trab_3m / 3

        ausencia_mes_1m      = aus_1m_real
        viagem_mes_1m        = viagem_1m
        reunioes_mes_1m      = reuniao_1m
        congressos_mes_1m    = congresso_1m
        treinamento_mes_1m   = treinamento_1m
        gestao_mes_1m        = gestao_1m
        pessoais_mes_1m      = pessoal_1m
        trabalhados_mes_1m   = trab_1m

        # === Mês PARCIAL (corrente em andamento) — separado de MAT/3m/1m ===
        # Útil pra ver "como está agora". NÃO contamina médias MAT (janela fechada).
        # IMPORTANTE: usar df_visitas direto (não vis_p), porque vis_p é filtrado pela
        # janela MAT que termina no fim do MES_FECHADO — visitas de maio nunca entrariam.
        n_visitas_parcial = 0
        mdms_visitados_parcial = []
        vis_dia_parcial = 0.0
        pct_aus_parcial = 0
        dias_decorridos_parcial = 0
        dias_uteis_parcial_completo = 0  # total do mês quando fechar

        # Ampliação: detalhamento por categoria no mês parcial (já prorrateado)
        ausencia_mes_parcial    = 0.0
        viagem_mes_parcial      = 0.0
        reunioes_mes_parcial    = 0.0
        congressos_mes_parcial  = 0.0
        treinamento_mes_parcial = 0.0
        gestao_mes_parcial      = 0.0
        pessoais_mes_parcial    = 0.0
        trabalhados_mes_parcial = 0.0

        if INCLUIR_MES_PARCIAL:
            ini_parcial = pd.Timestamp(MES_PARCIAL.year, MES_PARCIAL.month, 1)
            fim_parcial = pd.Timestamp(HOJE)  # até hoje (inclusive)

            # Pega visitas DIRETO do df_visitas (não filtrado pela janela MAT)
            vis_isid_total = df_visitas[df_visitas['ISID'] == isid]
            vis_parcial = vis_isid_total[
                (vis_isid_total['data'] >= ini_parcial) &
                (vis_isid_total['data'] <= fim_parcial)
            ]

            n_visitas_parcial = int(len(vis_parcial))
            mdms_visitados_parcial = sorted(set(str(m) for m in vis_parcial['mdm'].dropna()))

            # Dias úteis decorridos no mês até hoje
            dias_decorridos_parcial = sum(
                1 for d in pd.date_range(ini_parcial, fim_parcial) if eh_dia_util(d)
            )

            # === BUG FIX (mês parcial) ===
            # ANTES: usava aus_p (filtrado por janela MAT, que termina em MES_FECHADO).
            # Como MAT vai só até abril, maio nunca entrava → pct_ausencia_parcial = 0
            # para todo mundo. Aqui lemos df_ausencia_dia direto, filtrando pelo ISID
            # e pelo mês parcial.
            dias_uteis_parcial_completo = dias_uteis_mes(MES_PARCIAL.year, MES_PARCIAL.month)
            aus_isid_total = df_ausencia_dia[df_ausencia_dia['isid'] == isid]

            # Fator de prorrateamento — preserva semântica de "ritmo mensal projetado"
            fator_pp = (
                dias_decorridos_parcial / dias_uteis_parcial_completo
                if dias_uteis_parcial_completo > 0 else 0
            )

            if len(aus_isid_total):
                aus_parcial_filtro = aus_isid_total[
                    (aus_isid_total['ano'] == MES_PARCIAL.year) &
                    (aus_isid_total['mes'] == MES_PARCIAL.month)
                ]

                viagem_mes_parcial      = aus_parcial_filtro['fr_viagem'].sum()      * fator_pp
                reunioes_mes_parcial    = aus_parcial_filtro['fr_reuniao'].sum()     * fator_pp
                congressos_mes_parcial  = aus_parcial_filtro['fr_congresso'].sum()   * fator_pp
                treinamento_mes_parcial = aus_parcial_filtro['fr_treinamento'].sum() * fator_pp
                gestao_mes_parcial      = aus_parcial_filtro['fr_gestao'].sum()      * fator_pp
                pessoais_mes_parcial    = aus_parcial_filtro['fr_pessoal'].sum()     * fator_pp

                aus_parcial = (
                    viagem_mes_parcial + reunioes_mes_parcial + congressos_mes_parcial +
                    treinamento_mes_parcial + gestao_mes_parcial + pessoais_mes_parcial
                )
                ausencia_mes_parcial = aus_parcial
            else:
                aus_parcial = 0

            trab_parcial = max(1, dias_decorridos_parcial - aus_parcial)
            trabalhados_mes_parcial = trab_parcial
            vis_dia_parcial = (n_visitas_parcial / trab_parcial) if trab_parcial > 0 else 0
            pct_aus_parcial = round(100 * aus_parcial / dias_decorridos_parcial, 2) if dias_decorridos_parcial > 0 else 0
            
        # === Bases COMUNS de dias úteis por período ===
        # Lidas do UTEIS_COMUM (calculado fora do loop, igual pra todos).
        # Mantidas no dict do consultor para retrocompatibilidade do front,
        # mas a fonte de verdade agora é DATA.meta.
        uteis_total_comum_mat = UTEIS_COMUM['uteis_total_comum_mat']
        uteis_mes_comum_mat = UTEIS_COMUM['uteis_mes_comum_mat']

        uteis_total_comum_3m = UTEIS_COMUM['uteis_total_comum_3m']
        uteis_mes_comum_3m = UTEIS_COMUM['uteis_mes_comum_3m']

        uteis_total_comum_1m = UTEIS_COMUM['uteis_total_comum_1m']
        uteis_mes_comum_1m = UTEIS_COMUM['uteis_mes_comum_1m']

        uteis_total_comum_parcial = UTEIS_COMUM['uteis_total_comum_parcial']
        uteis_decorridos_comum_parcial = UTEIS_COMUM['uteis_decorridos_comum_parcial']
        uteis_mes_comum_parcial = UTEIS_COMUM['uteis_mes_comum_parcial']

        # === Quarters (Q0=corrente, Q-1=anterior, Q-2=2 anteriores) ===
        # Q corrente = mes_fechado.month → quarter
        q_corrente_num = (MES_FECHADO.month - 1) // 3 + 1
        q_corrente_ano = MES_FECHADO.year

        def quarter_range(ano, qnum):
            ini_m = (qnum - 1) * 3 + 1
            ini = pd.Timestamp(ano, ini_m, 1)
            if ini_m + 3 <= 12:
                fim = pd.Timestamp(ano, ini_m + 3, 1) - pd.Timedelta(days=1)
            else:
                fim = pd.Timestamp(ano + 1, ini_m + 3 - 12, 1) - pd.Timedelta(days=1)
            # Cap no janela_fim_ts (não pega futuro)
            fim_real = min(fim, janela_fim_ts)
            return ini, fim_real, f"{ano}-Q{qnum}"

        # Calcular Q0, Q-1, Q-2
        quarters_data = []
        for offset in [0, -1, -2, -3]:
            qn = q_corrente_num + offset
            qa = q_corrente_ano
            while qn <= 0:
                qn += 4
                qa -= 1
            ini, fim, label = quarter_range(qa, qn)
            vis_q = vis_p[(vis_p['data'] >= ini) & (vis_p['data'] <= fim)]
            mdms_q = sorted(set(str(m) for m in vis_q['mdm'].dropna()))

            # Freq granular: 1,2,3,4,5,6,7+
            freq_q = {f'n_med_{i}x': 0 for i in range(1, 7)}
            freq_q['n_med_7p'] = 0
            if len(vis_q):
                fpm = vis_q.groupby('mdm').size()
                for n in range(1, 7):
                    freq_q[f'n_med_{n}x'] = int((fpm == n).sum())
                freq_q['n_med_7p'] = int((fpm >= 7).sum())

            quarters_data.append({
                'label': label,
                'visitas': int(len(vis_q)),
                'medicos_unicos': len(mdms_q),
                'mdms': mdms_q,
                'ini': ini.strftime('%Y-%m-%d'),
                'fim': fim.strftime('%Y-%m-%d'),
                **freq_q,
            })

        # === Distribuição de frequência por médico (MAT — agrupada) ===
        if len(vis_p):
            freq_por_med = vis_p.groupby('mdm').size()
            n_med_1x = int((freq_por_med == 1).sum())
            n_med_2_3 = int(freq_por_med.between(2, 3).sum())
            n_med_4_6 = int(freq_por_med.between(4, 6).sum())
            n_med_7_plus = int((freq_por_med >= 7).sum())
        else:
            n_med_1x = n_med_2_3 = n_med_4_6 = n_med_7_plus = 0

        # Cidade/UF sede da estrutura (passa pra analisar_setor)
        # Tratar NaN (pandas.Series.get retorna NaN, não None)
        _cs_v = p.get('cidade_sede')
        _uf_v = p.get('uf_sede_estrutura')
        _st_v = p.get('cidade_sede_status', 'em_validacao')
        cidade_sede_clean = None if (pd.isna(_cs_v) or _cs_v is None) else str(_cs_v)
        uf_sede_clean = None if (pd.isna(_uf_v) or _uf_v is None) else str(_uf_v)
        status_clean = 'em_validacao' if (pd.isna(_st_v) or _st_v is None) else str(_st_v)

        rows.append({
            'ISID': isid,
            'nome': p['nome'],
            'sales_force': p['sales_force'],
            'territorio': p['territorio'],
            'gd_code': p['gd_code'],
            'gd_name': p['gd_name'],
            'win_id': p['win_id'],
            'hierarchy': p['hierarchy'],
            'cidade_sede': cidade_sede_clean,
            'uf_sede_estrutura': uf_sede_clean,
            'cidade_sede_status': status_clean,

            # MAT (12 meses)
            'visitas_12m': int(n_visitas),
            'medicos_unicos_12m': int(n_medicos_unicos),
            'dias_ativos_12m': int(n_dias_ativos),
            'uteis_12m': float(uteis_12m_total),
            'ausencia_12m': round(ausencia_12m, 2),
            'viagem_12m': round(viagem_12m, 2),
            'reunioes_12m': round(reuniao_12m, 2),
            'congressos_12m': round(congresso_12m, 2),
            'treinamento_12m': round(treinamento_12m, 2),
            'gestao_12m': round(gestao_12m, 2),
            'pessoais_12m': round(pessoal_12m, 2),
            'trabalhados_12m': round(trab_12m, 2),

            # Médias mensais
            'uteis_mes': round(uteis_mes_med, 2),
            'ausencia_mes': round(ausencia_mes_med, 2),
            'viagem_mes': round(viagem_mes_med, 2),
            'reunioes_mes': round(reuniao_mes_med, 2),
            'congressos_mes': round(congresso_mes_med, 2),
            'treinamento_mes': round(treinamento_mes_med, 2),
            'gestao_mes': round(gestao_mes_med, 2),
            'pessoais_mes': round(pessoal_mes_med, 2),
            'trabalhados_mes': round(trab_mes_med, 2),

            # Bases comuns de dias úteis para comparação visual no front
            'uteis_total_comum_mat': round(uteis_total_comum_mat, 2),
            'uteis_mes_comum_mat': round(uteis_mes_comum_mat, 2),
            'uteis_total_comum_3m': round(uteis_total_comum_3m, 2),
            'uteis_mes_comum_3m': round(uteis_mes_comum_3m, 2),
            'uteis_total_comum_1m': round(uteis_total_comum_1m, 2),
            'uteis_mes_comum_1m': round(uteis_mes_comum_1m, 2),
            'uteis_total_comum_parcial': round(uteis_total_comum_parcial, 2),
            'uteis_decorridos_comum_parcial': round(uteis_decorridos_comum_parcial, 2),
            'uteis_mes_comum_parcial': round(uteis_mes_comum_parcial, 2),

            'pct_ausencia': round(pct_ausencia, 2),
            'pct_trabalhados': round(pct_trab, 2),

            # Visitas/dia (a métrica certa: visitas / dias trabalhados)
            'vis_dia_media': round(vis_dia_media, 2),
            'vis_dia_mediana': round(vis_dia_mediana, 2),
            'vis_dia_max': round(vis_dia_max, 2),
            'cv_vis_dia': round(cv_vis_dia, 2),

            # Médicos
            'medicos_unicos_mes': round(medicos_unicos_mes, 2),
            'medicos_unicos_mes_painel': round(medicos_unicos_mes_painel, 2),
            'medicos_unicos_mes_taxa': round(medicos_unicos_mes_taxa, 2),
            'meses_ativos_efetivo': int(meses_ativos_efetivo),
            'freq_medico_mes': round(freq_medico_mes, 2),

            # Painel (proxy)
            'painel_size': int(painel_proxy_90d),
            'mdms_proxy_90d': mdms_proxy_90d,
            'painel_mes_fechado': int(painel_proxy_snap),
            'painel_proxy_metodo': 'visitas_90d',

            # Tendência
            'slope_vis_dia': round(slope, 4),
            'tendencia_vis_dia': tend,
            'slope_vis_dia_6m': round(slope_6m, 4),
            'tendencia_vis_dia_6m': tend_6m,
            'vd_3m_media': round(vd_3m_media, 2),
            'vd_6m_media': round(vd_6m_media, 2),
            'vd_6m_serie': vd_6m_serie,

            # Onda v3 — série de VISITAS/MÊS
            'visitas_mes_serie': visitas_mes_serie,
            'slope_window_n': slope_window_n,

            # Geografia
            'n_cidades_visitadas': int(n_cidades),
            'cidades_top5': cidades_top,

            # Lista de MDMs visitados MAT
            'mdms_visitados_mat': mdms_visitados_mat,
            'mdms_visitados_3m': mdms_visitados_3m,
            'mdms_visitados_1m': mdms_visitados_1m,

            # MÊS PARCIAL
            'mdms_visitados_parcial': mdms_visitados_parcial,

            # Volume de visitas por janela
            'visitas_3m': n_visitas_3m,
            'visitas_1m': n_visitas_1m,
            'visitas_parcial': n_visitas_parcial,
            'vis_dia_3m': round(vis_dia_3m, 2),
            'vis_dia_1m': round(vis_dia_1m, 2),
            'vis_dia_parcial': round(vis_dia_parcial, 2),

            # Ausência por janela
            'pct_ausencia_3m': pct_aus_3m,
            'pct_ausencia_1m': pct_aus_1m,
            'pct_ausencia_parcial': pct_aus_parcial,

            # Médias mensais detalhadas por janela
            'ausencia_mes_3m': round(ausencia_mes_3m, 2),
            'viagem_mes_3m': round(viagem_mes_3m, 2),
            'reunioes_mes_3m': round(reunioes_mes_3m, 2),
            'congressos_mes_3m': round(congressos_mes_3m, 2),
            'treinamento_mes_3m': round(treinamento_mes_3m, 2),
            'gestao_mes_3m': round(gestao_mes_3m, 2),
            'pessoais_mes_3m': round(pessoais_mes_3m, 2),
            'trabalhados_mes_3m': round(trabalhados_mes_3m, 2),

            'ausencia_mes_1m': round(ausencia_mes_1m, 2),
            'viagem_mes_1m': round(viagem_mes_1m, 2),
            'reunioes_mes_1m': round(reunioes_mes_1m, 2),
            'congressos_mes_1m': round(congressos_mes_1m, 2),
            'treinamento_mes_1m': round(treinamento_mes_1m, 2),
            'gestao_mes_1m': round(gestao_mes_1m, 2),
            'pessoais_mes_1m': round(pessoais_mes_1m, 2),
            'trabalhados_mes_1m': round(trabalhados_mes_1m, 2),

            'ausencia_mes_parcial': round(ausencia_mes_parcial, 2),
            'viagem_mes_parcial': round(viagem_mes_parcial, 2),
            'reunioes_mes_parcial': round(reunioes_mes_parcial, 2),
            'congressos_mes_parcial': round(congressos_mes_parcial, 2),
            'treinamento_mes_parcial': round(treinamento_mes_parcial, 2),
            'gestao_mes_parcial': round(gestao_mes_parcial, 2),
            'pessoais_mes_parcial': round(pessoais_mes_parcial, 2),
            'trabalhados_mes_parcial': round(trabalhados_mes_parcial, 2),

            # Metadata da parcial
            'parcial_dias_decorridos': dias_decorridos_parcial,
            'parcial_dias_uteis_total': dias_uteis_parcial_completo,
            'parcial_ym': f"{MES_PARCIAL.year:04d}-{MES_PARCIAL.month:02d}" if INCLUIR_MES_PARCIAL else None,

            # Quarters
            'quarters': quarters_data[::-1],

            # Distribuição de frequência por médico (MAT)
            'freq_dist_n_med_1x': n_med_1x,
            'freq_dist_n_med_2_3x': n_med_2_3,
            'freq_dist_n_med_4_6x': n_med_4_6,
            'freq_dist_n_med_7p': n_med_7_plus,
        })

    df_metr = pd.DataFrame(rows)
    return df_metr, UTEIS_COMUM

# ============================================================================
# 5. TIPO DE SETOR — baseado em comportamento real (cidades visitadas MAT)
# ============================================================================
def classificar_tipo_setor(df_metr, df_visitas):
    """
    Classifica cada consultor como Local / Misto / Viagem
    com base no NÚMERO DE CIDADES distintas visitadas no MAT.

    UF não é populado no relatório de visitas explicitamente — derivamos via
    contagem de cidades como proxy (UF requer enriquecimento externo).

    Regras:
      Local:  cidades <= TIPO_LOCAL_MAX_CIDADES
      Viagem: cidades >= TIPO_VIAGEM_MIN_CIDADES
      Misto:  entre
    """
    audit = []
    tipos = []
    for _, row in df_metr.iterrows():
        nc = row['n_cidades_visitadas']
        if nc <= TIPO_LOCAL_MAX_CIDADES:
            tipo = 'Local'
        elif nc >= TIPO_VIAGEM_MIN_CIDADES:
            tipo = 'Viagem'
        else:
            tipo = 'Misto'
        tipos.append(tipo)
        audit.append({
            'ISID': row['ISID'],
            'nome': row['nome'],
            'sales_force': row['sales_force'],
            'n_cidades_visitadas': nc,
            'visitas_12m': row['visitas_12m'],
            'cidades_top5': str(row['cidades_top5']),
            'tipo_setor': tipo,
            'regra': f'≤{TIPO_LOCAL_MAX_CIDADES} cidades→Local · ≥{TIPO_VIAGEM_MIN_CIDADES}→Viagem · senão Misto'
        })
    df_metr['tipo_setor'] = tipos
    return df_metr, pd.DataFrame(audit)


# ============================================================================
# 6. TEMPO NO SETOR — via relatorio_brickagem.csv (Sales Area Effective Date)
# ============================================================================
def calcular_meses_no_setor(df_metr, path_brickagem=None):
    """
    Calcula meses entre Sales Area Effective Date e o mês fechado.

    Lógica:
      - Para cada consultor, pegar TERRITORY_VEEVA (= Sales Area Code dele)
      - Buscar no brickagem o Sales Area Effective Date desse SA (data de criação)
      - meses = diff entre essa data e MES_FECHADO

    NOTA: 'Sales Area Effective Date' é a data em que o SETOR (sales area) foi
    criado/efetivado. NÃO é exatamente "data em que o consultor X assumiu o SA Y" —
    se um SA foi criado em 2018 e o consultor entrou nele em 2024, dará 8 anos.
    Mesmo assim é melhor que 'tempo na empresa' (ACC ADMISSION DATE) que tinha antes.

    Se houver fonte com 'data de movimento do consultor', basta substituir aqui.
    """
    if path_brickagem is None:
        path_brickagem = IN('relatorio_brickagem.csv')

    meses = []
    data_eff = []
    metodo = []

    if not os.path.exists(path_brickagem):
        print(f"    AVISO: {path_brickagem} não encontrado — meses_no_setor ficará null")
        for _ in df_metr.itertuples():
            meses.append(None); data_eff.append(None); metodo.append(None)
        df_metr['meses_no_setor'] = meses
        df_metr['admissao'] = data_eff
        df_metr['fonte_admissao'] = metodo
        return df_metr

    df_br = pd.read_csv(path_brickagem, sep=';', encoding='utf-8', dtype=str)
    df_br.columns = [c.strip() for c in df_br.columns]
    df_br['eff_dt'] = pd.to_datetime(df_br['Sales Area Effective Date'],
                                     format='%d/%m/%Y', errors='coerce')
    # Pra cada SA, pegar a data MAIS ANTIGA (mais conservador — quando o SA começou)
    sa_to_eff = (df_br.groupby('Sales Area Sales Area Code')['eff_dt']
                 .min().to_dict())

    for _, row in df_metr.iterrows():
        sa = row.get('territorio')  # = TERRITORY_VEEVA
        eff = sa_to_eff.get(sa)
        if pd.notna(eff):
            anos = MES_FECHADO.year - eff.year
            ms = MES_FECHADO.month - eff.month
            total = anos * 12 + ms
            meses.append(int(total))
            data_eff.append(eff.strftime('%Y-%m-%d'))
            metodo.append('sales_area_effective_date')
        else:
            meses.append(None); data_eff.append(None); metodo.append(None)

    df_metr['meses_no_setor'] = meses
    df_metr['admissao'] = data_eff
    df_metr['fonte_admissao'] = metodo
    n_pop = sum(1 for m in meses if m is not None)
    print(f"    meses_no_setor populado em {n_pop}/{len(df_metr)} consultores "
          f"(fonte: Sales Area Effective Date)")
    return df_metr


# ============================================================================
# 5B. LOOKUP CIDADE → UF (para classificação real de setor)
# ============================================================================
# Cobre capitais + cidades >150k habitantes + cidades médicas relevantes.
# Cidades fora desta lista marcam UF como "??" e são contadas separadamente.

CIDADE_UF = {
    # Norte
    'MANAUS':'AM','BELEM':'PA','PORTO VELHO':'RO','RIO BRANCO':'AC','BOA VISTA':'RR',
    'MACAPA':'AP','PALMAS':'TO','ANANINDEUA':'PA','SANTAREM':'PA','MARABA':'PA',
    'PARAUAPEBAS':'PA','CASTANHAL':'PA','MARITUBA':'PA','BARCARENA':'PA',
    'JI PARANA':'RO','PORTO VELHO':'RO','MANACAPURU':'AM','PARINTINS':'AM',
    'ITACOATIARA':'AM','TEFE':'AM','TABATINGA':'AM','ARARAQUARA':'SP',  # ajustes regionais
    # Nordeste
    'SALVADOR':'BA','FORTALEZA':'CE','RECIFE':'PE','SAO LUIS':'MA','MACEIO':'AL',
    'NATAL':'RN','JOAO PESSOA':'PB','TERESINA':'PI','ARACAJU':'SE',
    'FEIRA DE SANTANA':'BA','VITORIA DA CONQUISTA':'BA','CAMACARI':'BA','JUAZEIRO':'BA',
    'ILHEUS':'BA','LAURO DE FREITAS':'BA','TEIXEIRA DE FREITAS':'BA','ITABUNA':'BA',
    'JEQUIE':'BA','BARREIRAS':'BA','PORTO SEGURO':'BA','VALENCA':'BA','ALAGOINHAS':'BA',
    'JABOATAO DOS GUARARAPES':'PE','OLINDA':'PE','CARUARU':'PE','PETROLINA':'PE',
    'PAULISTA':'PE','CABO DE SANTO AGOSTINHO':'PE','CAMARAGIBE':'PE','GARANHUNS':'PE',
    'CAUCAIA':'CE','MARACANAU':'CE','JUAZEIRO DO NORTE':'CE','SOBRAL':'CE','CRATO':'CE',
    'IGUATU':'CE','MARANGUAPE':'CE','ITAPIPOCA':'CE','QUIXADA':'CE',
    'IMPERATRIZ':'MA','SAO JOSE DE RIBAMAR':'MA','TIMON':'MA','CAXIAS':'MA',
    'CACAPAVA':'SP',  # Cuidado: existe Caçapava SP
    'CAMPINA GRANDE':'PB','PATOS':'PB','SANTA RITA':'PB','BAYEUX':'PB',
    'PARNAIBA':'PI','PICOS':'PI','FLORIANO':'PI',
    'MOSSORO':'RN','PARNAMIRIM':'RN','CAICO':'RN','SAO GONCALO DO AMARANTE':'RN',
    'NOSSA SENHORA DO SOCORRO':'SE','LAGARTO':'SE','ITABAIANA':'SE',
    'ARAPIRACA':'AL','PALMEIRA DOS INDIOS':'AL','RIO LARGO':'AL',
    # Centro-Oeste
    'BRASILIA':'DF','BRASÍLIA':'DF','GOIANIA':'GO','CAMPO GRANDE':'MS','CUIABA':'MT',
    'APARECIDA DE GOIANIA':'GO','ANAPOLIS':'GO','LUZIANIA':'GO','RIO VERDE':'GO',
    'AGUAS LINDAS DE GOIAS':'GO','VALPARAISO DE GOIAS':'GO','TRINDADE':'GO',
    'FORMOSA':'GO','NOVO GAMA':'GO','SENADOR CANEDO':'GO','ITUMBIARA':'GO',
    'CATALAO':'GO','JATAI':'GO','PLANALTINA':'GO','CALDAS NOVAS':'GO',
    'DOURADOS':'MS','TRES LAGOAS':'MS','PONTA PORA':'MS','CORUMBA':'MS','NAVIRAI':'MS',
    'NOVA ANDRADINA':'MS','PARANAIBA':'MS','SIDROLANDIA':'MS',
    'VARZEA GRANDE':'MT','RONDONOPOLIS':'MT','SINOP':'MT','TANGARA DA SERRA':'MT',
    'CACERES':'MT','SORRISO':'MT','LUCAS DO RIO VERDE':'MT','PRIMAVERA DO LESTE':'MT',
    'BARRA DO GARCAS':'MT','ALTA FLORESTA':'MT',
    'GAMA':'DF','TAGUATINGA':'DF','CEILANDIA':'DF',
    # Sudeste
    'SAO PAULO':'SP','SÃO PAULO':'SP','RIO DE JANEIRO':'RJ','BELO HORIZONTE':'MG','VITORIA':'ES','VITÓRIA':'ES',
    'GUARULHOS':'SP','CAMPINAS':'SP','SAO BERNARDO DO CAMPO':'SP','SANTO ANDRE':'SP','OSASCO':'SP',
    'SAO JOSE DOS CAMPOS':'SP','RIBEIRAO PRETO':'SP','SOROCABA':'SP','SANTOS':'SP',
    'MAUA':'SP','SAO JOSE DO RIO PRETO':'SP','MOGI DAS CRUZES':'SP','DIADEMA':'SP',
    'JUNDIAI':'SP','PIRACICABA':'SP','CARAPICUIBA':'SP','BAURU':'SP','ITAQUAQUECETUBA':'SP',
    'SAO VICENTE':'SP','FRANCA':'SP','GUARUJA':'SP','TAUBATE':'SP','LIMEIRA':'SP',
    'SUZANO':'SP','SUMARE':'SP','BARUERI':'SP','EMBU DAS ARTES':'SP','SAO CARLOS':'SP',
    'INDAIATUBA':'SP','COTIA':'SP','AMERICANA':'SP','MARILIA':'SP','ARACATUBA':'SP',
    'JACAREI':'SP','PRESIDENTE PRUDENTE':'SP','ITAPEVI':'SP','RIO CLARO':'SP',
    'FERRAZ DE VASCONCELOS':'SP','ITU':'SP','BRAGANCA PAULISTA':'SP','FRANCISCO MORATO':'SP',
    'PINDAMONHANGABA':'SP','FRANCO DA ROCHA':'SP','BOTUCATU':'SP','CATANDUVA':'SP',
    'JAU':'SP','JAÚ':'SP','ATIBAIA':'SP','OURINHOS':'SP','POA':'SP','SERTAOZINHO':'SP',
    'TATUI':'SP','VOTORANTIM':'SP','SAO CAETANO DO SUL':'SP','SAO JOAO DA BOA VISTA':'SP',
    'NITEROI':'RJ','NITERÓI':'RJ','SAO GONCALO':'RJ','SÃO GONÇALO':'RJ','DUQUE DE CAXIAS':'RJ',
    'NOVA IGUACU':'RJ','BELFORD ROXO':'RJ','SAO JOAO DE MERITI':'RJ','PETROPOLIS':'RJ',
    'PETRÓPOLIS':'RJ','VOLTA REDONDA':'RJ','MAGE':'RJ','MACAE':'RJ','MACAÉ':'RJ',
    'ITABORAI':'RJ','CABO FRIO':'RJ','CAMPOS DOS GOYTACAZES':'RJ','NOVA FRIBURGO':'RJ',
    'BARRA MANSA':'RJ','TERESOPOLIS':'RJ','TERESÓPOLIS':'RJ','RESENDE':'RJ','ANGRA DOS REIS':'RJ',
    'NILOPOLIS':'RJ','MESQUITA':'RJ','QUEIMADOS':'RJ','MARICA':'RJ','RIO DAS OSTRAS':'RJ',
    'ITAPERUNA':'RJ','SAQUAREMA':'RJ','ARARUAMA':'RJ','MARICÁ':'RJ',
    'CONTAGEM':'MG','UBERLANDIA':'MG','JUIZ DE FORA':'MG','BETIM':'MG','MONTES CLAROS':'MG',
    'RIBEIRAO DAS NEVES':'MG','UBERABA':'MG','SETE LAGOAS':'MG','DIVINOPOLIS':'MG',
    'IPATINGA':'MG','SANTA LUZIA':'MG','IBIRITE':'MG','POCOS DE CALDAS':'MG',
    'PATOS DE MINAS':'MG','POUSO ALEGRE':'MG','TEOFILO OTONI':'MG','BARBACENA':'MG',
    'GOVERNADOR VALADARES':'MG','VARGINHA':'MG','CONSELHEIRO LAFAIETE':'MG',
    'VESPASIANO':'MG','ITABIRA':'MG','NOVA LIMA':'MG','PASSOS':'MG','ARAGUARI':'MG',
    'ITAJUBA':'MG','LAVRAS':'MG','SETE LAGOAS':'MG','MURIAE':'MG',
    'VILA VELHA':'ES','SERRA':'ES','CARIACICA':'ES','LINHARES':'ES','SAO MATEUS':'ES',
    'COLATINA':'ES','GUARAPARI':'ES','VIANA':'ES','CACHOEIRO DE ITAPEMIRIM':'ES',
    # Sul
    'CURITIBA':'PR','PORTO ALEGRE':'RS','FLORIANOPOLIS':'SC','FLORIANÓPOLIS':'SC',
    'LONDRINA':'PR','MARINGA':'PR','MARINGÁ':'PR','PONTA GROSSA':'PR','CASCAVEL':'PR',
    'SAO JOSE DOS PINHAIS':'PR','FOZ DO IGUACU':'PR','COLOMBO':'PR','GUARAPUAVA':'PR',
    'PARANAGUA':'PR','APUCARANA':'PR','TOLEDO':'PR','UMUARAMA':'PR','CAMPO LARGO':'PR',
    'ARAUCARIA':'PR','ARAPONGAS':'PR','PINHAIS':'PR','PIRAQUARA':'PR','SAO JOSE':'SC',
    'JOINVILLE':'SC','BLUMENAU':'SC','CHAPECO':'SC','ITAJAI':'SC','ITAJAÍ':'SC',
    'CRICIUMA':'SC','CRICIÚMA':'SC','LAGES':'SC','PALHOCA':'SC','BALNEARIO CAMBORIU':'SC',
    'BRUSQUE':'SC','TUBARAO':'SC','SAO BENTO DO SUL':'SC','CACADOR':'SC','RIO DO SUL':'SC',
    'JARAGUA DO SUL':'SC','CONCORDIA':'SC','GASPAR':'SC',
    'CANOAS':'RS','PELOTAS':'RS','CAXIAS DO SUL':'RS','GRAVATAI':'RS','SANTA MARIA':'RS',
    'NOVO HAMBURGO':'RS','VIAMAO':'RS','SAO LEOPOLDO':'RS','RIO GRANDE':'RS',
    'ALVORADA':'RS','PASSO FUNDO':'RS','SAPUCAIA DO SUL':'RS','ESTEIO':'RS',
    'BAGE':'RS','URUGUAIANA':'RS','SANTA CRUZ DO SUL':'RS','CACHOEIRINHA':'RS',
    'BENTO GONCALVES':'RS','VACARIA':'RS','GUAIBA':'RS','CACHOEIRA DO SUL':'RS',
    'CARAZINHO':'RS','SAPIRANGA':'RS','ERECHIM':'RS','IJUI':'RS','TORRES':'RS',
}


CIDADES_EXTRA = {
    # Interior SP — oncologia
    'BARRETOS':'SP','ASSIS':'SP','JALES':'SP','FERNANDOPOLIS':'SP','BONFIM PAULISTA':'SP',
    'OURINHOS':'SP','TUPA':'SP','BIRIGUI':'SP','PENAPOLIS':'SP','ANDRADINA':'SP',
    'OLIMPIA':'SP','BEBEDOURO':'SP','MOCOCA':'SP','ITAPEVA':'SP','REGISTRO':'SP',
    'PIRACAIA':'SP','BEBEDOURO':'SP','REGISTRO':'SP','ITARARE':'SP','LINS':'SP',
    'AVARE':'SP','CAPAO BONITO':'SP','SOROCABA':'SP','SAO JOAQUIM DA BARRA':'SP',
    # Interior MG
    'POCOS DE CALDAS':'MG','PASSOS':'MG','LAVRAS':'MG','BARBACENA':'MG','UBA':'MG',
    'TEOFILO OTONI':'MG','VICOSA':'MG','TIMOTEO':'MG','JANUARIA':'MG','UNAI':'MG',
    'PARACATU':'MG','UBA':'MG','UBERLANDIA':'MG','UBERABA':'MG','ALFENAS':'MG',
    # Interior RJ
    'ITAPERUNA':'RJ','BARRA MANSA':'RJ','RESENDE':'RJ','PARATY':'RJ','TRES RIOS':'RJ',
    # Interior PR
    'CIANORTE':'PR','PARANAVAI':'PR','UMUARAMA':'PR','TOLEDO':'PR','MEDIANEIRA':'PR',
    'IRATI':'PR','CAMPO MOURAO':'PR','TELEMACO BORBA':'PR','CORNELIO PROCOPIO':'PR',
    # Interior SC
    'XANXERE':'SC','VIDEIRA':'SC','MAFRA':'SC','TIMBO':'SC','INDAIAL':'SC',
    # Interior RS
    'BAGE':'RS','LIVRAMENTO':'RS','SANTA ROSA':'RS','SANTO ANGELO':'RS','CRUZ ALTA':'RS',
    'TRES PASSOS':'RS','SANTANA DO LIVRAMENTO':'RS','ROSARIO DO SUL':'RS',
    # Interior BA
    'BARREIRAS':'BA','BOM JESUS DA LAPA':'BA','EUNAPOLIS':'BA','VITORIA DA CONQUISTA':'BA',
    # Nordeste outros
    'GARANHUNS':'PE','CARUARU':'PE','SERRA TALHADA':'PE','PETROLINA':'PE',
    'JUAZEIRO DO NORTE':'CE','SOBRAL':'CE','CRATO':'CE',
    # Centro-Oeste
    'GOIANIA':'GO','ANAPOLIS':'GO','RIO VERDE':'GO','CATALAO':'GO','ITUMBIARA':'GO',
    'JATAI':'GO','LUZIANIA':'GO','NIQUELANDIA':'GO','GUAPÓ':'GO',
}

# Mesclar
CIDADE_UF.update(CIDADES_EXTRA)


def _normalizar_cidade(s):
    """Remove acentos e padroniza pra uppercase."""
    if not s or pd.isna(s):
        return None
    import unicodedata
    s = str(s).upper().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s


def derivar_uf(cidade):
    """Cidade → UF. Normaliza acentos antes do lookup. '??' se desconhecida."""
    norm = _normalizar_cidade(cidade)
    if not norm:
        return None
    return CIDADE_UF.get(norm, '??')



# ============================================================================
# ESTRUTURAS HISTÓRICAS — leitura e cruzamento para meses_no_setor correto
# ============================================================================
#
# Pasta esperada: C:/Users/delimajr/OneDrive - Merck Sharp & Dohme LLC/
#                 Desktop/PY/healthcheck/bases
# Arquivos no formato: MM_AAAA-ESTRUTURA-FV.csv
# Colunas esperadas (mesmo padrão dos CSVs compartilhados):
#   WEIN ID (ou WEIN), SALES FORCE, TERRITORY, NAME, BU, HIERARCHY, etc.
#
# Lógica para meses_no_setor v2:
#   1. Para cada consultora (chave = WEIN ID), rastreamos todos os arquivos
#      históricos onde ela aparece, ordenados por data (MM_AAAA).
#   2. Detectamos quebra de equipe (SALES FORCE mudou entre meses consecutivos).
#   3. meses_no_setor = número de meses consecutivos na equipe atual,
#      contando a partir do último mês em que a equipe mudou.
#      Se nunca mudou → tempo total desde o primeiro arquivo em que aparece.
#   Exemplo Juliana: aparece abr/26 como BR_ENCAMINHADORES e mai/26 como BR_GI_HN
#   → quebra detectada em mai/26 → meses_no_setor = 1 (só mai/26)
# ============================================================================

PASTA_ESTRUTURAS = os.path.join(
    os.path.expanduser('~'),
    'OneDrive - Merck Sharp & Dohme LLC',
    'Desktop', 'PY', 'healthcheck', 'bases'
)

# ============================================================================
# ONDA v7 — Tratamento de Trocas de Sales Force (excecoes_trocas_sf.csv)
# ============================================================================
# REGRAS:
#   - 'rename' / 'fusao' → reescreve sf_antes para sf_depois RETROATIVAMENTE
#     em todos os arquivos históricos. Métricas do consultor continuam contínuas.
#   - 'troca_real' → consultor mudou de área. MAT individual é RECORTADO a partir
#     do mês_quebra. Badge "trocou de SF" no payload.
#   - 'ignorar' → suprime esse caso (não trata como troca).
#
# O CSV é gerado pelo script diagnostico_e_csv_trocas.py e editado manualmente.
# ============================================================================

def _str_csv(v):
    """Helper: converte valor de célula CSV (que pode ser NaN, None, str ou número)
    para string limpa. Evita AttributeError quando célula está vazia (NaN/float)."""
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def ler_excecoes_trocas_sf(path: str = None) -> dict:
    """
    Lê bases/excecoes_trocas_sf.csv e retorna:
        {
          'renames': [(sf_antes, sf_depois), ...],   # globais (aplicam em todo histórico)
          'trocas_reais': {wein_id: {'mes_quebra': (ano,mes), 'sf_antes': str, 'sf_depois': str}},
          'fusoes': [(sf_antes, sf_depois), ...],    # tratadas como rename
          'ignorados': [wein_id, ...],
        }

    Se o arquivo não existir, retorna estrutura vazia (comportamento atual mantido).
    """
    if path is None:
        path = os.path.join(PASTA_ESTRUTURAS, 'excecoes_trocas_sf.csv')

    result = {'renames': [], 'fusoes': [], 'trocas_reais': {}, 'ignorados': []}
    if not os.path.isfile(path):
        print(f"    excecoes_trocas_sf.csv: não encontrado → {path}")
        print(f"    Comportamento: histórico usado como está (sem renames/trocas explícitas).")
        return result

    try:
        df = pd.read_csv(path, sep=';', encoding='utf-8', dtype=str)
    except Exception as e:
        print(f"    ⚠️  Erro lendo excecoes_trocas_sf.csv: {e}")
        return result

    df.columns = [c.strip().lower() for c in df.columns]
    for col in ['wein_id', 'mes_quebra', 'sf_antes', 'sf_depois', 'tipo']:
        if col not in df.columns:
            print(f"    ⚠️  excecoes_trocas_sf.csv sem coluna '{col}' — ignorando arquivo.")
            return result

    cnt = {'rename': 0, 'fusao': 0, 'troca_real': 0, 'ignorar': 0, 'invalido': 0}

    for _, r in df.iterrows():
        tipo = _str_csv(r.get('tipo')).lower()
        sf_antes = _str_csv(r.get('sf_antes'))
        sf_depois = _str_csv(r.get('sf_depois'))

        if tipo == 'rename':
            par = (sf_antes.upper(), sf_depois)
            if par not in [(a.upper(), b) for a, b in result['renames']]:
                result['renames'].append((sf_antes, sf_depois))
            cnt['rename'] += 1

        elif tipo == 'fusao':
            par = (sf_antes.upper(), sf_depois)
            if par not in [(a.upper(), b) for a, b in result['fusoes']]:
                result['fusoes'].append((sf_antes, sf_depois))
            cnt['fusao'] += 1

        elif tipo == 'troca_real':
            try:
                wid = int(float(r['wein_id']))
            except (ValueError, TypeError):
                cnt['invalido'] += 1
                continue
            mes_q = _str_csv(r.get('mes_quebra'))
            m = re.match(r'^(\d{4})[/-](\d{1,2})$', mes_q)
            if not m:
                cnt['invalido'] += 1
                continue
            ano_q, mes_n_q = int(m.group(1)), int(m.group(2))
            result['trocas_reais'][wid] = {
                'mes_quebra': (ano_q, mes_n_q),
                'sf_antes': sf_antes,
                'sf_depois': sf_depois,
                'observacao': _str_csv(r.get('observacao')),
            }
            cnt['troca_real'] += 1

        elif tipo == 'ignorar':
            try:
                wid = int(float(r['wein_id']))
                result['ignorados'].append(wid)
            except (ValueError, TypeError):
                pass
            cnt['ignorar'] += 1

        else:
            cnt['invalido'] += 1

    print(f"    excecoes_trocas_sf.csv carregado: "
          f"renames={cnt['rename']} fusoes={cnt['fusao']} "
          f"trocas_reais={cnt['troca_real']} ignorar={cnt['ignorar']} "
          f"invalido={cnt['invalido']}")
    if result['renames']:
        renames_unicos = set((a, b) for a, b in result['renames'])
        print(f"    Renames distintos: {sorted(renames_unicos)}")
    if result['fusoes']:
        fusoes_unicos = set((a, b) for a, b in result['fusoes'])
        print(f"    Fusões distintas: {sorted(fusoes_unicos)}")
    return result


def aplicar_renames_no_historico(historico: dict, excecoes: dict) -> dict:
    """
    Reescreve sales_force_hist nos arquivos históricos aplicando renames e fusões.
    Trata renames como globais (não dependem do consultor que disparou).
    Retorna o mesmo dict de histórico modificado in-place.
    """
    todos_renames = excecoes.get('renames', []) + excecoes.get('fusoes', [])
    if not todos_renames:
        return historico

    # Mapa de substituição: chave uppercase
    sub_map = {}
    for sf_antes, sf_depois in todos_renames:
        sub_map[sf_antes.strip().upper()] = sf_depois.strip()

    total_reescritas = 0
    for (ano, mes), df_h in historico.items():
        if 'sales_force_hist' not in df_h.columns:
            continue
        antes = df_h['sales_force_hist'].copy()
        # Aplicar substituição
        def _sub(v):
            if v is None or pd.isna(v):
                return v
            key = str(v).strip().upper()
            return sub_map.get(key, v)
        df_h['sales_force_hist'] = df_h['sales_force_hist'].apply(_sub)
        reescritas = (antes != df_h['sales_force_hist']).sum()
        total_reescritas += reescritas

    print(f"    aplicar_renames_no_historico: {total_reescritas} células reescritas em {len(historico)} arquivos.")
    return historico


def aplicar_renames_no_snapshot_atual(df_universo: pd.DataFrame, excecoes: dict) -> pd.DataFrame:
    """
    Aplica os mesmos renames/fusões no snapshot atual.
    Necessário para coerência: se BR_TUMORES_MAMA foi renomeada para
    BR_TUMORES_FEMININOS_MAMA, mas o snapshot ainda tem BR_TUMORES_MAMA por algum
    motivo, garantimos consistência.
    """
    todos_renames = excecoes.get('renames', []) + excecoes.get('fusoes', [])
    if not todos_renames:
        return df_universo
    sub_map = {a.strip().upper(): b.strip() for a, b in todos_renames}
    n_antes = (df_universo['sales_force'].str.upper().isin(sub_map.keys())).sum()
    df_universo['sales_force'] = df_universo['sales_force'].apply(
        lambda v: sub_map.get(str(v).strip().upper(), v) if v is not None else v
    )
    if n_antes > 0:
        print(f"    aplicar_renames_no_snapshot_atual: {n_antes} consultores tiveram SF reescrita.")
    return df_universo


# ============================================================================
# ONDA v8 — Tratamento de Trocas de GD (excecoes_trocas_gd.csv)
# ============================================================================
# Quando um consultor mudou de GD mantendo a mesma SF, pode ter sido:
#   - 'fusao'      → consequência de fusão de SF (Alair Cristina). Sem badge.
#   - 'troca_real' → reorganização geográfica real (caso Fabiola). Badge + recorte.
#   - 'ignorar'    → suprime essa detecção.
#
# REGRA DE RECORTE COMBINADO (decisão de produto):
# Se consultor tem 'troca_real' em AMBOS SF e GD, recorta MAT pela TROCA MAIS
# RECENTE (padrão dos relatórios da equipe).
# ============================================================================

def ler_excecoes_trocas_gd(path: str = None) -> dict:
    """
    Lê bases/excecoes_trocas_gd.csv e retorna:
        {
          'trocas_reais': {wein_id: {'mes_quebra': (ano,mes), 'gd_antes': str,
                                       'gd_depois': str, 'sf': str}},
          'ignorados': [wein_id, ...],
        }
    Se arquivo não existe, retorna estrutura vazia.
    """
    if path is None:
        path = os.path.join(PASTA_ESTRUTURAS, 'excecoes_trocas_gd.csv')

    result = {'trocas_reais': {}, 'ignorados': []}
    if not os.path.isfile(path):
        print(f"    excecoes_trocas_gd.csv: não encontrado → {path}")
        print(f"    Comportamento: trocas de GD não detectadas.")
        return result

    try:
        df = pd.read_csv(path, sep=';', encoding='utf-8', dtype=str)
    except Exception as e:
        print(f"    ⚠️  Erro lendo excecoes_trocas_gd.csv: {e}")
        return result

    df.columns = [c.strip().lower() for c in df.columns]
    for col in ['wein_id', 'mes_quebra', 'gd_antes', 'gd_depois', 'tipo']:
        if col not in df.columns:
            print(f"    ⚠️  excecoes_trocas_gd.csv sem coluna '{col}' — ignorando arquivo.")
            return result

    cnt = {'fusao': 0, 'troca_real': 0, 'ignorar': 0, 'invalido': 0}
    for _, r in df.iterrows():
        tipo = _str_csv(r.get('tipo')).lower()

        if tipo == 'fusao':
            # Fusão de GD não dispara recorte nem badge — operação contínua
            cnt['fusao'] += 1
            continue

        elif tipo == 'troca_real':
            try:
                wid = int(float(r['wein_id']))
            except (ValueError, TypeError):
                cnt['invalido'] += 1
                continue
            mes_q = _str_csv(r.get('mes_quebra'))
            m = re.match(r'^(\d{4})[/-](\d{1,2})$', mes_q)
            if not m:
                cnt['invalido'] += 1
                continue
            ano_q, mes_n_q = int(m.group(1)), int(m.group(2))
            result['trocas_reais'][wid] = {
                'mes_quebra': (ano_q, mes_n_q),
                'gd_antes': _str_csv(r.get('gd_antes')),
                'gd_depois': _str_csv(r.get('gd_depois')),
                'sf': _str_csv(r.get('sf')),
                'observacao': _str_csv(r.get('observacao')),
            }
            cnt['troca_real'] += 1

        elif tipo == 'ignorar':
            try:
                wid = int(float(r['wein_id']))
                result['ignorados'].append(wid)
            except (ValueError, TypeError):
                pass
            cnt['ignorar'] += 1

        else:
            cnt['invalido'] += 1

    print(f"    excecoes_trocas_gd.csv carregado: "
          f"fusao={cnt['fusao']} trocas_reais={cnt['troca_real']} "
          f"ignorar={cnt['ignorar']} invalido={cnt['invalido']}")
    return result


def calcular_corte_combinado(excecoes_sf: dict, excecoes_gd: dict) -> dict:
    """
    REGRA: para cada wein_id que tem troca_real em SF e/ou GD, devolve a data
    da troca mais RECENTE (decisão de produto — padrão dos relatórios da equipe).

    Retorna dict: {wein_id: {'mes_quebra': (ano, mes), 'origem': 'sf'|'gd'|'sf_e_gd'}}
    """
    combinado = {}
    trocas_sf_real = excecoes_sf.get('trocas_reais', {})
    trocas_gd_real = excecoes_gd.get('trocas_reais', {})

    todos_wids = set(trocas_sf_real.keys()) | set(trocas_gd_real.keys())
    for wid in todos_wids:
        info_sf = trocas_sf_real.get(wid)
        info_gd = trocas_gd_real.get(wid)

        if info_sf and info_gd:
            # Tem ambos → pegar a mais RECENTE
            if info_sf['mes_quebra'] >= info_gd['mes_quebra']:
                combinado[wid] = {'mes_quebra': info_sf['mes_quebra'], 'origem': 'sf_e_gd_pega_sf'}
            else:
                combinado[wid] = {'mes_quebra': info_gd['mes_quebra'], 'origem': 'sf_e_gd_pega_gd'}
        elif info_sf:
            combinado[wid] = {'mes_quebra': info_sf['mes_quebra'], 'origem': 'sf'}
        elif info_gd:
            combinado[wid] = {'mes_quebra': info_gd['mes_quebra'], 'origem': 'gd'}

    return combinado


def ler_estruturas_historicas(pasta: str = None) -> dict:
    """
    Lê todos os arquivos MM_AAAA-ESTRUTURA-FV.csv da pasta e retorna
    um dict ordenado {(ano, mes): DataFrame}.
    Colunas normalizadas: wein_id (int), sales_force, territory, nome, bu, hierarchy
    """
    if pasta is None:
        pasta = PASTA_ESTRUTURAS

    historico = {}
    if not os.path.isdir(pasta):
        print(f"    AVISO ler_estruturas_historicas: pasta não encontrada → {pasta}")
        return historico

    import glob
    pattern = os.path.join(pasta, '*-ESTRUTURA-FV.csv')
    arquivos = glob.glob(pattern)
    if not arquivos:
        print(f"    AVISO: nenhum arquivo *-ESTRUTURA-FV.csv encontrado em {pasta}")
        return historico

    for arq in sorted(arquivos):
        nome_arq = os.path.basename(arq)
        # Formato esperado: MM_AAAA-ESTRUTURA-FV.csv
        m = re.match(r'^(\d{2})_(\d{4})-ESTRUTURA-FV\.csv$', nome_arq)
        if not m:
            continue
        mes_n, ano_n = int(m.group(1)), int(m.group(2))
        try:
            df = pd.read_csv(arq, sep=';', encoding='utf-8', dtype=str)
        except Exception:
            try:
                df = pd.read_csv(arq, sep=',', encoding='utf-8', dtype=str)
            except Exception as e:
                print(f"    AVISO: não foi possível ler {nome_arq}: {e}")
                continue

        df.columns = [c.strip().upper() for c in df.columns]

        # Normalizar coluna WEIN ID (pode vir como WEIN, WIN ID, WEIN ID)
        wein_col = None
        for c in ['ACC WEIN ID', 'WEIN', 'WIN ID', 'WIN']:
            if c in df.columns:
                wein_col = c
                break
        if wein_col is None:
            print(f"    AVISO: {nome_arq} sem coluna WEIN ID/WEIN/WIN ID — pulado")
            continue

        df['wein_id'] = pd.to_numeric(df[wein_col], errors='coerce')

        # Normalizar sales_force
        sf_col = next((c for c in ['SALES FORCE', 'SALESFORCE', 'SF'] if c in df.columns), None)
        df['sales_force_hist'] = df[sf_col].str.strip() if sf_col else None

        # Normalizar territory
        terr_col = next((c for c in ['TERRITORY', 'TERRITÓRIO', 'TERRITORIO'] if c in df.columns), None)
        df['territory_hist'] = df[terr_col].str.strip() if terr_col else None

        # Filtrar BU ONCOLOGIA se coluna existir
        if 'BU' in df.columns:
            df = df[df['BU'].str.strip().str.upper() == BU_ALVO].copy()

        historico[(ano_n, mes_n)] = df

    chaves_ord = sorted(historico.keys())
    if not chaves_ord:
        print(f"    AVISO: Nenhuma estrutura histórica carregada com sucesso (0 arquivos válidos).")
        return historico
    print(f"    Estruturas históricas carregadas: {len(chaves_ord)} arquivos "
          f"({chaves_ord[0][0]}/{chaves_ord[0][1]:02d} → "
          f"{chaves_ord[-1][0]}/{chaves_ord[-1][1]:02d})")
    # Retornar como OrderedDict cronológico
    from collections import OrderedDict
    return OrderedDict((k, historico[k]) for k in chaves_ord)


def calcular_meses_no_setor_v2(df_metr: pd.DataFrame,
                                historico: dict,
                                mes_ref: 'date' = None,
                                trocas_csv: dict = None) -> pd.DataFrame:
    """
    Calcula meses_no_setor cruzando o histórico de estruturas via WEIN ID.

    Para cada consultor:
      - Rastreia a série de SALES FORCE nos arquivos históricos (ordem cronológica)
      - Detecta a última quebra de equipe (mudança de SALES FORCE)
      - meses_no_setor = meses consecutivos na equipe ATUAL desde a última quebra
      - Se nunca houve quebra → meses desde o primeiro arquivo em que aparece
      - Se wein_id ausente ou nunca apareceu → fallback para função original

    PARÂMETRO ADICIONAL (Onda v7):
      trocas_csv: dict opcional retornado por ler_excecoes_trocas_sf().
                  Se um consultor está em trocas_csv['trocas_reais'], usa essa
                  data como mes_troca_sf. Se está em 'ignorados', NÃO detecta troca.
                  Se a quebra do histórico foi classificada como rename/fusão no
                  CSV (e renames já foram aplicados no histórico antes), o
                  histórico será contínuo e não detectará quebra.

    Também preenche:
      sales_force_hist   — equipe no mês mais recente do histórico
      territory_hist     — território no mês mais recente
      meses_setor_metodo — 'historico_sem_quebra' | 'historico_pos_quebra' | 'fallback'
      mes_troca_sf       — (ano, mes) da troca, ou None se não trocou
      sf_anterior        — SF anterior à última troca, ou None
      trocou_sf_no_mat   — True se a troca aconteceu dentro da janela MAT
    """
    if mes_ref is None:
        mes_ref = MES_FECHADO

    if not historico:
        print("    calcular_meses_no_setor_v2: sem histórico — usando fallback")
        df_metr['meses_setor_metodo'] = 'fallback'
        return df_metr

    chaves = list(historico.keys())   # [(ano,mes), ...] já ordenado
    trocas_csv = trocas_csv or {}
    trocas_reais_csv = trocas_csv.get('trocas_reais', {})
    ignorados_csv = set(trocas_csv.get('ignorados', []))

    # Janela MAT para determinar se a troca está dentro dela
    # mes_ref = último mês fechado. MAT começa 11 meses antes (12m fechados).
    mes_ref_y, mes_ref_m = mes_ref.year, mes_ref.month
    janela_ini_y = mes_ref_y - 1
    janela_ini_m = mes_ref_m + 1   # ex: ref=abr/26 → MAT começa mai/25
    if janela_ini_m > 12:
        janela_ini_m -= 12
        janela_ini_y += 1
    # Limite superior = mês CORRENTE (inclui mês parcial), não mês fechado.
    # Razão: troca de mai/26 deve disparar badge mesmo com MES_FECHADO=abr/26,
    # porque o HTML mostra mai/26 parcial. Mantém coerência visual.
    from datetime import date as _date
    _hoje = _date.today()
    mes_corrente_y, mes_corrente_m = _hoje.year, _hoje.month
    def _dentro_mat(ano, mes):
        return ((ano, mes) >= (janela_ini_y, janela_ini_m)
                and (ano, mes) <= (mes_corrente_y, mes_corrente_m))

    meses_list, metodo_list, sf_hist_list, terr_hist_list = [], [], [], []
    mes_troca_list, sf_anterior_list, trocou_mat_list = [], [], []

    for _, row in df_metr.iterrows():
        wein = row.get('win_id')
        if pd.isna(wein) or wein is None:
            meses_list.append(row.get('meses_no_setor'))
            metodo_list.append('fallback_sem_wein')
            sf_hist_list.append(row.get('sales_force'))
            terr_hist_list.append(row.get('territorio'))
            mes_troca_list.append(None)
            sf_anterior_list.append(None)
            trocou_mat_list.append(False)
            continue

        wein = int(wein)

        # Montar série cronológica [(ano, mes, sales_force, territory)]
        serie = []
        for (ano, mes), df_h in historico.items():
            mask = df_h['wein_id'] == wein
            hits = df_h[mask]
            if len(hits) > 0:
                sf  = hits['sales_force_hist'].iloc[0]  if 'sales_force_hist' in hits else None
                ter = hits['territory_hist'].iloc[0]    if 'territory_hist'   in hits else None
                serie.append((ano, mes, sf, ter))

        if not serie:
            # Consultor não apareceu em nenhum histórico → fallback
            meses_list.append(row.get('meses_no_setor'))
            metodo_list.append('fallback_sem_historico')
            sf_hist_list.append(row.get('sales_force'))
            terr_hist_list.append(row.get('territorio'))
            mes_troca_list.append(None)
            sf_anterior_list.append(None)
            trocou_mat_list.append(False)
            continue

        # SF e território do arquivo mais recente
        sf_atual_hist  = serie[-1][2]
        ter_atual_hist = serie[-1][3]

        # Verificar se consultor está marcado como IGNORAR no CSV
        if wein in ignorados_csv:
            ano_ini, mes_ini = serie[0][0], serie[0][1]
            total = (mes_ref.year - ano_ini) * 12 + (mes_ref.month - mes_ini)
            meses_list.append(max(1, total))
            metodo_list.append('ignorado_csv')
            sf_hist_list.append(sf_atual_hist)
            terr_hist_list.append(ter_atual_hist)
            mes_troca_list.append(None)
            sf_anterior_list.append(None)
            trocou_mat_list.append(False)
            continue

        # Detectar última quebra de equipe (de trás pra frente)
        # ATENÇÃO: os renames já foram aplicados em historico (Onda v7), então
        # qualquer quebra que ainda for detectada é troca REAL.
        ultimo_mes_quebra_idx = None
        sf_anterior_quebra = None
        for i in range(len(serie)-1, 0, -1):
            sf_ant = serie[i-1][2]
            sf_now = serie[i][2]
            if sf_ant and sf_now and sf_ant.strip().upper() != sf_now.strip().upper():
                ultimo_mes_quebra_idx = i   # índice em que a mudança CHEGOU
                sf_anterior_quebra = sf_ant
                break

        if ultimo_mes_quebra_idx is not None:
            # Meses desde o arquivo da quebra (inclusive) até mes_ref
            ano_q, mes_q = serie[ultimo_mes_quebra_idx][0], serie[ultimo_mes_quebra_idx][1]
            total = (mes_ref.year - ano_q) * 12 + (mes_ref.month - mes_q)
            meses_list.append(max(1, total))
            metodo_list.append('historico_pos_quebra')
            mes_troca_list.append((ano_q, mes_q))
            sf_anterior_list.append(sf_anterior_quebra)
            trocou_mat_list.append(_dentro_mat(ano_q, mes_q))
        else:
            # Nunca mudou de equipe → contar desde a primeira aparição
            ano_ini, mes_ini = serie[0][0], serie[0][1]
            total = (mes_ref.year - ano_ini) * 12 + (mes_ref.month - mes_ini)
            meses_list.append(max(1, total))
            metodo_list.append('historico_sem_quebra')
            mes_troca_list.append(None)
            sf_anterior_list.append(None)
            trocou_mat_list.append(False)

        sf_hist_list.append(sf_atual_hist)
        terr_hist_list.append(ter_atual_hist)

    df_metr = df_metr.copy()
    df_metr['meses_no_setor']      = meses_list
    df_metr['meses_setor_metodo']  = metodo_list
    df_metr['sales_force_hist']    = sf_hist_list
    df_metr['territory_hist']      = terr_hist_list
    df_metr['mes_troca_sf']        = mes_troca_list     # (ano, mes) ou None
    df_metr['sf_anterior']         = sf_anterior_list   # str ou None
    df_metr['trocou_sf_no_mat']    = trocou_mat_list    # bool

    n_pop    = sum(1 for m in meses_list if m is not None)
    n_quebra = sum(1 for m in metodo_list if m == 'historico_pos_quebra')
    n_trocou_mat = sum(1 for v in trocou_mat_list if v)
    print(f"    meses_no_setor v2: {n_pop}/{len(df_metr)} populados "
          f"({n_quebra} com quebra detectada, {n_trocou_mat} dentro do MAT)")
    return df_metr


def enriquecer_troca_gd(df_metr: pd.DataFrame, excecoes_gd: dict,
                          mes_ref=None) -> pd.DataFrame:
    """
    ONDA v8: Adiciona ao df_metr os campos relacionados a troca de GD.
    Esses campos NÃO substituem os de SF — são complementares.

    Campos adicionados:
      trocou_gd_no_mat   — True se troca de GD foi dentro da janela MAT
      mes_troca_gd       — (ano, mes) da troca, ou None
      gd_anterior        — nome do GD anterior, ou None

    Também atualiza mat_efetivo_meses para considerar a TROCA MAIS RECENTE
    entre SF e GD (decisão de produto: padrão da equipe).
    """
    if mes_ref is None:
        mes_ref = MES_FECHADO

    trocas_gd_real = (excecoes_gd or {}).get('trocas_reais', {})

    # Janela MAT (mesmo cálculo do v2)
    mes_ref_y, mes_ref_m = mes_ref.year, mes_ref.month
    janela_ini_y = mes_ref_y - 1
    janela_ini_m = mes_ref_m + 1
    if janela_ini_m > 12:
        janela_ini_m -= 12
        janela_ini_y += 1
    # Limite superior = mês CORRENTE (inclui mês parcial), não mês fechado.
    # Razão: troca de mai/26 deve disparar badge mesmo com MES_FECHADO=abr/26,
    # porque o HTML mostra mai/26 parcial. Mantém coerência visual.
    from datetime import date as _date
    _hoje = _date.today()
    mes_corrente_y, mes_corrente_m = _hoje.year, _hoje.month
    def _dentro_mat(ano, mes):
        return ((ano, mes) >= (janela_ini_y, janela_ini_m)
                and (ano, mes) <= (mes_corrente_y, mes_corrente_m))

    trocou_gd_list, mes_troca_gd_list, gd_anterior_list = [], [], []

    for _, row in df_metr.iterrows():
        wid = row.get('win_id')
        if pd.isna(wid):
            trocou_gd_list.append(False)
            mes_troca_gd_list.append(None)
            gd_anterior_list.append(None)
            continue

        wid_int = int(wid)
        info = trocas_gd_real.get(wid_int)
        if not info:
            trocou_gd_list.append(False)
            mes_troca_gd_list.append(None)
            gd_anterior_list.append(None)
            continue

        ano_q, mes_q = info['mes_quebra']
        trocou_gd_list.append(_dentro_mat(ano_q, mes_q))
        mes_troca_gd_list.append((ano_q, mes_q))
        gd_anterior_list.append(info.get('gd_antes'))

    df_metr = df_metr.copy()
    df_metr['trocou_gd_no_mat'] = trocou_gd_list
    df_metr['mes_troca_gd']     = mes_troca_gd_list
    df_metr['gd_anterior']      = gd_anterior_list

    n_trocou_gd = sum(1 for v in trocou_gd_list if v)
    print(f"    enriquecer_troca_gd: {n_trocou_gd} consultores com troca real de GD no MAT")

    # === Atualizar meses_no_setor para refletir TROCA MAIS RECENTE ===
    # Se consultor tem ambos SF e GD como troca_real, usa o mais recente
    n_ajustados = 0
    for idx, row in df_metr.iterrows():
        mes_sf = row.get('mes_troca_sf')
        mes_gd = row.get('mes_troca_gd')
        if mes_sf is None and mes_gd is None:
            continue
        # Pegar o mais recente
        candidatos = [m for m in [mes_sf, mes_gd] if m is not None]
        if not candidatos:
            continue
        mais_recente = max(candidatos)
        # Recalcular meses_no_setor desde essa data
        ano_r, mes_r = mais_recente
        novo_meses = (mes_ref.year - ano_r) * 12 + (mes_ref.month - mes_r)
        novo_meses = max(1, novo_meses)
        if row.get('meses_no_setor') != novo_meses:
            df_metr.at[idx, 'meses_no_setor'] = novo_meses
            n_ajustados += 1
    if n_ajustados > 0:
        print(f"    Ajustes em meses_no_setor (troca mais recente SF/GD): {n_ajustados}")

    return df_metr


def calcular_historico_periodos(df_metr: pd.DataFrame,
                                  df_visitas: pd.DataFrame,
                                  df_ausencia_dia: pd.DataFrame,
                                  excecoes_sf: dict,
                                  excecoes_gd: dict,
                                  mes_ref=None) -> dict:
    """
    ONDA v9: Para cada consultor com troca_real (SF ou GD) confirmada,
    calcula métricas dos DOIS últimos períodos (atual + anterior),
    permitindo comparação antes/depois.

    Retorna dict {ISID: [period_atual, period_anterior]} onde cada period é:
        {
          'label':       'Mai/26 — atual' | 'Mai/25 a Abr/26',
          'tipo':        'atual' | 'anterior',
          'sf':          str,
          'gd_nome':     str | None,
          'data_ini':    str ISO,
          'data_fim':    str ISO,
          'meses':       int,
          'metricas': {
            'visitas': int,
            'dias_trabalhados': float,
            'vis_dia': float,
            'medicos_unicos': int,
            'novos_por_dia': float,
            'freq_por_medico': float,
            'pct_cidade_sede': float,
            'pct_uf_sede': float,
            'pct_dias_trabalhados': float,
          }
        }

    Só inclui consultores com troca real em SF ou GD detectada pelos CSVs.
    """
    if mes_ref is None:
        mes_ref = MES_FECHADO

    trocas_sf = (excecoes_sf or {}).get('trocas_reais', {})
    trocas_gd = (excecoes_gd or {}).get('trocas_reais', {})

    # Fim da janela MAT (último dia do MES_FECHADO)
    if mes_ref.month == 12:
        janela_fim_ts = pd.Timestamp(mes_ref.year, 12, 31)
    else:
        janela_fim_ts = pd.Timestamp(mes_ref.year, mes_ref.month + 1, 1) - pd.Timedelta(days=1)

    # Cidade sede e UF sede do consultor (do snapshot atual)
    # Necessário para % cidade sede e % UF sede históricos
    sede_map = {}   # ISID → (cidade_sede, uf_sede)
    for _, row in df_metr.iterrows():
        sede_map[row['ISID']] = (
            _str_csv(row.get('cidade_sede')).upper(),
            _str_csv(row.get('uf_sede')).upper(),
        )

    historico = {}

    for _, row in df_metr.iterrows():
        wid = row.get('win_id')
        isid = row.get('ISID')
        if pd.isna(wid) or not isid:
            continue
        wid_int = int(wid)

        # === Determinar data da troca mais recente (consolidando SF e GD) ===
        info_sf = trocas_sf.get(wid_int)
        info_gd = trocas_gd.get(wid_int)
        if not info_sf and not info_gd:
            continue   # consultor sem troca real → não entra no histórico

        # Pegar data da troca mais recente
        candidatos = []
        if info_sf:
            candidatos.append(('sf', info_sf))
        if info_gd:
            candidatos.append(('gd', info_gd))
        # Mais recente = maior tupla (ano, mes)
        candidatos.sort(key=lambda x: x[1]['mes_quebra'], reverse=True)
        tipo_troca_recente, info_recente = candidatos[0]
        ano_q, mes_q = info_recente['mes_quebra']

        # === Definir os DOIS períodos ===
        # Período ATUAL: do mês da troca até MES_FECHADO
        data_ini_atual = pd.Timestamp(ano_q, mes_q, 1)
        data_fim_atual = janela_fim_ts

        # Período ANTERIOR: até a véspera da troca (limitado a 12 meses antes)
        data_fim_anterior = data_ini_atual - pd.Timedelta(days=1)
        # Início do anterior = 12 meses antes da troca (ou JANELA_INI, o que for mais recente)
        ano_ini_ant = ano_q - 1
        mes_ini_ant = mes_q
        data_ini_anterior = pd.Timestamp(ano_ini_ant, mes_ini_ant, 1)
        if data_ini_anterior < pd.Timestamp(JANELA_INI):
            data_ini_anterior = pd.Timestamp(JANELA_INI)

        # === SF e GD de cada período ===
        # Período atual = SF/GD atuais do snapshot
        sf_atual = _str_csv(row.get('sales_force')) or '—'
        gd_atual = _str_csv(row.get('gd_name')) or _str_csv(row.get('NOME GD')) or None

        # Período anterior = SF/GD anteriores conforme CSVs
        sf_anterior = _str_csv(info_sf['sf_antes']) if info_sf else sf_atual
        gd_anterior = _str_csv(info_gd['gd_antes']) if info_gd else gd_atual

        # === Calcular métricas para cada período ===
        cidade_sede, uf_sede = sede_map.get(isid, ('', ''))

        def calc_periodo(data_ini, data_fim, sf_label, gd_label, tipo):
            # Filtrar visitas do período
            vis_p = df_visitas[
                (df_visitas['ISID'] == isid) &
                (df_visitas['data'] >= data_ini) &
                (df_visitas['data'] <= data_fim)
            ]
            # Filtrar ausências do período
            aus_p = df_ausencia_dia[
                (df_ausencia_dia['isid'] == isid) &
                (pd.to_datetime(df_ausencia_dia['data']) >= data_ini) &
                (pd.to_datetime(df_ausencia_dia['data']) <= data_fim)
            ]

            n_visitas = int(len(vis_p))
            n_medicos = int(vis_p['mdm'].nunique()) if len(vis_p) else 0

            # Dias úteis do período (somar mês a mês)
            dias_uteis_periodo = 0
            cursor = pd.Timestamp(data_ini.year, data_ini.month, 1)
            fim_loop = pd.Timestamp(data_fim.year, data_fim.month, 1)
            while cursor <= fim_loop:
                dias_uteis_periodo += dias_uteis_mes(cursor.year, cursor.month)
                # Próximo mês
                if cursor.month == 12:
                    cursor = pd.Timestamp(cursor.year + 1, 1, 1)
                else:
                    cursor = pd.Timestamp(cursor.year, cursor.month + 1, 1)
            # Ausência (em dias)
            ausencia_dias = float(aus_p['fr_total'].sum()) if 'fr_total' in aus_p.columns else 0
            dias_trabalhados = max(0, dias_uteis_periodo - ausencia_dias)
            vis_dia = (n_visitas / dias_trabalhados) if dias_trabalhados > 0 else 0
            pct_dias_trabalhados = (dias_trabalhados / dias_uteis_periodo * 100) if dias_uteis_periodo > 0 else 0

            # Novos médicos por dia (amplitude)
            novos_por_dia = (n_medicos / dias_trabalhados) if dias_trabalhados > 0 else 0
            # Frequência por médico (profundidade)
            freq_por_medico = (n_visitas / n_medicos) if n_medicos > 0 else 0

            # Disciplina geográfica
            # As colunas 'cidade' e 'uf' não existem em df_visitas — usar 'call_city'
            # e derivar UF como em enriquecer_geo_consultor.
            if len(vis_p) and cidade_sede:
                cidades_norm = vis_p['call_city'].fillna('').astype(str).str.upper().str.strip()
                vis_cidade = (cidades_norm == cidade_sede).sum()
                pct_cidade = float(vis_cidade / len(vis_p) * 100)
            else:
                pct_cidade = 0.0

            if len(vis_p) and uf_sede:
                # Derivar UF a partir da cidade (mesma lógica de enriquecer_geo_consultor)
                ufs_derivadas = vis_p['call_city'].map(derivar_uf)
                vis_uf = (ufs_derivadas == uf_sede).sum()
                pct_uf = float(vis_uf / len(vis_p) * 100)
            else:
                pct_uf = 0.0

            # Label do período (formato pt-BR)
            meses_pt = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
            yi, mi = data_ini.year, data_ini.month
            yf, mf = data_fim.year, data_fim.month
            if (yi, mi) == (yf, mf):
                label_dt = f"{meses_pt[mi-1]}/{str(yi)[2:]}"
            else:
                label_dt = f"{meses_pt[mi-1]}/{str(yi)[2:]} a {meses_pt[mf-1]}/{str(yf)[2:]}"
            label = label_dt + (' — atual' if tipo == 'atual' else '')

            # Meses do período
            n_meses = (yf - yi) * 12 + (mf - mi) + 1

            return {
                'label': label,
                'tipo': tipo,
                'sf': sf_label,
                'gd_nome': gd_label,
                'data_ini': data_ini.strftime('%Y-%m-%d'),
                'data_fim': data_fim.strftime('%Y-%m-%d'),
                'meses': int(n_meses),
                'metricas': {
                    'visitas': n_visitas,
                    'dias_uteis': float(dias_uteis_periodo),
                    'dias_trabalhados': round(dias_trabalhados, 1),
                    'vis_dia': round(vis_dia, 2),
                    'medicos_unicos': n_medicos,
                    'novos_por_dia': round(novos_por_dia, 2),
                    'freq_por_medico': round(freq_por_medico, 2),
                    'pct_cidade_sede': round(pct_cidade, 1),
                    'pct_uf_sede': round(pct_uf, 1),
                    'pct_dias_trabalhados': round(pct_dias_trabalhados, 1),
                },
            }

        per_atual = calc_periodo(data_ini_atual, data_fim_atual, sf_atual, gd_atual, 'atual')
        per_anterior = calc_periodo(data_ini_anterior, data_fim_anterior, sf_anterior, gd_anterior, 'anterior')

        historico[isid] = [per_atual, per_anterior]

    print(f"    calcular_historico_periodos: {len(historico)} consultores com histórico comparativo")
    return historico


def enriquecer_geo_consultor(df_metr, df_visitas, pct_uf_significativa=5.0):
    """
    Para cada consultor:
      - n_ufs_visitadas, n_ufs_significativas (≥5%), n_ufs_significativas_10pct (≥10%)
      - pct_visitas_uf_principal, pct_visitas_cidade_principal
      - ufs_top, cidades_top5
    """
    geo_rows = []
    for isid in df_metr['ISID']:
        vis_p = df_visitas[df_visitas['ISID']==isid].copy()
        if len(vis_p)==0:
            geo_rows.append({'ISID':isid,'n_ufs_visitadas':0,
                             'n_ufs_significativas':0,'n_ufs_significativas_10pct':0,
                             'ufs_top':{}, 'cidades_top5':{},
                             'pct_visitas_uf_principal':0.0,
                             'pct_visitas_cidade_principal':0.0,
                             'pct_visitas_uf_desconhecida':0.0})
            continue
        vis_p['uf'] = vis_p['call_city'].map(derivar_uf)
        total_vis = len(vis_p)
        uf_desconhecida_n = (vis_p['uf']=='??').sum()
        pct_uf_desconhecida = round(100*uf_desconhecida_n/total_vis, 1)

        ufs_validas = vis_p[vis_p['uf'].notna() & (vis_p['uf']!='??')]
        n_ufs = ufs_validas['uf'].nunique()
        ufs_top = ufs_validas['uf'].value_counts().head(4).to_dict()
        ufs_counts = ufs_validas['uf'].value_counts()
        ufs_signif = (ufs_counts / total_vis * 100 >= pct_uf_significativa).sum()
        ufs_signif_10 = (ufs_counts / total_vis * 100 >= 10).sum()  # NOVO
        if ufs_top:
            uf_principal_vis = max(ufs_top.values())
            pct_principal = round(100*uf_principal_vis/total_vis, 1)
        else:
            pct_principal = 0.0

        # Cidades (NOVO: % cidade principal)
        cidades_validas = vis_p[vis_p['call_city'].notna() & (vis_p['call_city']!='')]
        cidades_top5 = cidades_validas['call_city'].value_counts().head(5).to_dict()
        if cidades_top5:
            cid_pri_vis = max(cidades_top5.values())
            pct_cid_pri = round(100*cid_pri_vis/total_vis, 1)
        else:
            pct_cid_pri = 0.0

        geo_rows.append({
            'ISID': isid,
            'n_ufs_visitadas': int(n_ufs),
            'n_ufs_significativas': int(ufs_signif),
            'n_ufs_significativas_10pct': int(ufs_signif_10),
            'ufs_top': ufs_top,
            'cidades_top5': cidades_top5,
            'pct_visitas_uf_principal': pct_principal,
            'pct_visitas_cidade_principal': pct_cid_pri,
            'pct_visitas_uf_desconhecida': pct_uf_desconhecida,
        })
    df_geo = pd.DataFrame(geo_rows)
    df_metr = df_metr.merge(df_geo, on='ISID', how='left')
    return df_metr


def classificar_tipo_setor_v2(df_metr):
    """
    Regra v3 — 3 categorias:
      Local:              ≥80% das visitas concentradas em UMA cidade (ou ≤1 cidade visitada)
      Viagem Interna:     várias cidades, mas MESMA UF principal (concentração de UF ≥80%) — intra-estadual
      Viagem Interestadual: ≥2 UFs com ≥10% das visitas (precisa aéreo, alto deslocamento)

    Mantém compatibilidade: campo 'tipo_setor' ainda existe; os 3 valores são
    'Local', 'Viagem Interna', 'Viagem Interestadual'.
    """
    tipos = []
    audit_rows = []
    for _, row in df_metr.iterrows():
        nc = row.get('n_cidades_visitadas', 0) or 0
        nu = row.get('n_ufs_visitadas', 0) or 0
        pct_uf_pri = row.get('pct_visitas_uf_principal', 100.0) or 100.0
        pct_cid_pri = row.get('pct_visitas_cidade_principal', 0.0) or 0.0
        nus_10 = row.get('n_ufs_significativas_10pct', 0) or 0  # novo: UFs com ≥10%

        # 1) Local: ≥80% das visitas em 1 cidade
        if nc <= 1 or pct_cid_pri >= 80:
            tipo = 'Local'
            justif = f'{pct_cid_pri:.0f}% das visitas em 1 cidade'
        # 2) Viagem Interestadual: ≥2 UFs com ≥10% (precisa aéreo)
        elif nus_10 >= 2:
            tipo = 'Viagem Interestadual'
            justif = f'{nus_10} UFs com ≥10% das visitas · UF principal {pct_uf_pri:.0f}%'
        # 3) Viagem Interna: várias cidades, mas concentrado em 1 UF
        else:
            tipo = 'Viagem Interna'
            justif = f'{nc} cidades · {pct_uf_pri:.0f}% concentração em 1 UF'

        tipos.append(tipo)
        audit_rows.append({
            'ISID': row['ISID'],
            'nome': row['nome'],
            'sales_force': row['sales_force'],
            'n_cidades_visitadas': nc,
            'n_ufs_visitadas': nu,
            'n_ufs_signif_10pct': nus_10,
            'pct_visitas_uf_principal': pct_uf_pri,
            'pct_visitas_cidade_principal': pct_cid_pri,
            'ufs_top': str(row.get('ufs_top',{})),
            'cidades_top5': str(row.get('cidades_top5',{})),
            'tipo_setor': tipo,
            'justificativa': justif,
        })
    df_metr['tipo_setor'] = tipos
    return df_metr, pd.DataFrame(audit_rows)


# ============================================================================
# 7. SÉRIES TEMPORAIS (team)
# ============================================================================
def calcular_series_team(df_visitas, df_ausencia_dia, universo):
    """
    Para cada mês entre 2024-01 e MES_FECHADO:
      - visitas: total visitas, médicos únicos (DEDUPE global!), consultores ativos, vis/dia team
      - ausencia: úteis, ausencia total, breakdown, %ausencia, consultores ativos
      - painel: painel total snapshot (proxy), painel medio por consultor
    """
    series_visitas = []
    series_ausencia = []
    series_painel = []

    isids_univ = set(universo['ISID'])

    # Limite: até MES_FECHADO inclusive
    cursor = date(2024, 1, 1)
    while cursor <= MES_FECHADO:
        ano, mes = cursor.year, cursor.month
        ym = f"{ano:04d}-{mes:02d}"
        # Início e fim do mês
        ini = pd.Timestamp(ano, mes, 1)
        fim = ini + pd.offsets.MonthEnd(0)

        # Visitas do mês
        vis_m = df_visitas[(df_visitas['data']>=ini) & (df_visitas['data']<=fim)]
        n_visitas = len(vis_m)
        n_medicos_unicos_time = vis_m['mdm'].nunique()
        consultores_ativos = vis_m['ISID'].nunique()

        # Dias úteis do mês × consultores ativos (proxy)
        uteis_mes = dias_uteis_mes(ano, mes)

        # Ausência do mês (no universo)
        aus_m = df_ausencia_dia[(df_ausencia_dia['ano']==ano)&(df_ausencia_dia['mes']==mes)]
        ausencia_m = aus_m['fr_total'].sum()
        viagem_m = aus_m['fr_viagem'].sum()
        reuniao_m = aus_m['fr_reuniao'].sum()
        congresso_m = aus_m['fr_congresso'].sum()
        treinamento_m = aus_m['fr_treinamento'].sum()
        gestao_m = aus_m['fr_gestao'].sum()
        pessoal_m = aus_m['fr_pessoal'].sum()
        consultores_ativos_aus = aus_m['isid'].nunique()

        # Dias trabalhados team = uteis_mes * n_universo - ausencia_total
        n_univ = len(isids_univ)
        uteis_total_team = uteis_mes * n_univ
        trab_total = max(0, uteis_total_team - ausencia_m)
        pct_aus = (ausencia_m / uteis_total_team * 100) if uteis_total_team else 0

        # Vis/dia team = visitas / dias trabalhados (FÓRMULA CORRETA)
        vis_dia_team = n_visitas / trab_total if trab_total > 0 else 0

        series_visitas.append({
            'ym': ym,
            'visitas': int(n_visitas),
            'medicos_unicos_time': int(n_medicos_unicos_time),  # DEDUPE global do time
            'consultores_ativos': int(consultores_ativos),
            'vis_dia_team': round(vis_dia_team, 2),
        })

        series_ausencia.append({
            'ym': ym,
            'uteis': uteis_total_team,
            'ausencia': round(ausencia_m, 1),
            'viagem': round(viagem_m, 1),
            'reunioes': round(reuniao_m, 1),
            'congressos': round(congresso_m, 1),
            'treinamento': round(treinamento_m, 1),
            'gestao': round(gestao_m, 1),
            'pessoais': round(pessoal_m, 1),
            'trabalhados': round(trab_total, 1),
            'pct_ausencia': round(pct_aus, 1),
            'consultores_ativos_aus': int(consultores_ativos_aus),
            'ausencia_media_cons': round(ausencia_m / max(1, consultores_ativos_aus), 2),
            'trabalhados_media_cons': round(trab_total / max(1, n_univ), 2),
        })

        # Painel: snapshot proxy = médicos únicos visitados nos 90 dias até fim
        cutoff_90 = fim - pd.Timedelta(days=90)
        vis_90 = df_visitas[(df_visitas['data']>=cutoff_90) & (df_visitas['data']<=fim)]
        painel_total_proxy = vis_90['mdm'].nunique()
        # Painel médio por consultor (medianos da janela)
        painel_por_cons = vis_90.groupby('ISID')['mdm'].nunique()
        painel_medio = float(painel_por_cons.mean()) if len(painel_por_cons) else 0
        painel_mediano = float(painel_por_cons.median()) if len(painel_por_cons) else 0

        series_painel.append({
            'ym': ym,
            'painel_total_time': int(painel_total_proxy),  # dedupe global proxy
            'painel_medio_consultor': round(painel_medio, 1),
            'painel_mediano_consultor': round(painel_mediano, 1),
            'consultores_no_calc': int(len(painel_por_cons)),
        })

        # Avançar mês
        if mes == 12:
            cursor = date(ano+1, 1, 1)
        else:
            cursor = date(ano, mes+1, 1)

    # Filtrar meses sem dados — se um mês tem 0 visitas no time inteiro,
    # quer dizer que não foi carregado relatório daquele mês (não foi atividade real).
    # Sem isso, a timeline mostra 2024 inteiro como zero e fica confuso.
    series_visitas = [r for r in series_visitas if r.get('visitas', 0) > 0]
    if series_visitas:
        ym_min = series_visitas[0]['ym']
        ym_max = series_visitas[-1]['ym']
        series_ausencia = [r for r in series_ausencia if r['ym'] >= ym_min and r['ym'] <= ym_max]
        series_painel   = [r for r in series_painel   if r['ym'] >= ym_min and r['ym'] <= ym_max]

    return {
        'visitas': series_visitas,
        'ausencia': series_ausencia,
        'painel': series_painel,
    }


def _carregar_meta_mccp_f2f(path_mccp, universo_isids=None):
    """
    Lê a meta planejada F2F por (ISID, MDM, ciclo) do relatorio_mccp.csv.
    Retorna dict {(isid, mdm, 'YYYY-Qn'): meta_int}. É a base da regra global de
    cobertura: um médico só conta no mês enquanto não cumpriu a meta do ciclo.
    """
    if not (path_mccp and os.path.exists(path_mccp)):
        return {}
    df = _ler_mccp_cob(path_mccp, universo_isids)
    if df.empty:
        return {}
    df = df[df['_canal'].astype(str).str.lower().str.contains('face')]
    out = {}
    for _, r in df.iterrows():
        isid = str(r.get('ISID') or '').upper().strip()
        mdm = str(r.get('ACC MDM ID') or '').strip()
        ano, q = r.get('_ano'), r.get('_q')
        if not isid or not mdm or mdm.upper() in ('', 'NAN', 'NONE') or not ano or not q:
            continue
        try:
            meta = float(r.get('_meta') or 0)
        except (TypeError, ValueError):
            meta = 0
        key = (isid, mdm, f"{ano}-{q}")
        out[key] = max(out.get(key, 0), meta)
    return out


def marcar_medicos_cob_mensal(df_visitas, meta_lookup):
    """
    Cobertura mensal DENTRO da frequência planejada (definição global de leitura).
    Para cada (consultor, médico, ciclo trimestral), ordena as visitas por data e
    marca como "no plano" apenas as primeiras `meta` (F2F do MCCP). Toques além da
    meta — ex.: médico freq-1 já visitado em janeiro, revisitado em fevereiro — são
    extra e NÃO contam. Retorna dict {(isid, ym): nº de médicos únicos no plano no mês}.
    Médico sem plano no painel tem meta=0 → nunca conta (cobertura é só do painel).
    """
    if not meta_lookup:
        return {}
    df = df_visitas[['ISID', 'mdm', 'data']].dropna(subset=['data']).copy()
    if df.empty:
        return {}
    df['mdm'] = df['mdm'].astype(str).str.strip()
    df['ym'] = df['data'].dt.strftime('%Y-%m')
    df['cycle'] = df['data'].dt.year.astype(str) + '-Q' + (((df['data'].dt.month - 1) // 3) + 1).astype(str)
    df = df.sort_values(['ISID', 'mdm', 'cycle', 'data'])
    df['rank'] = df.groupby(['ISID', 'mdm', 'cycle']).cumcount() + 1
    df['meta'] = [meta_lookup.get((i, m, c), 0) for i, m, c in zip(df['ISID'], df['mdm'], df['cycle'])]
    inplan = df[df['rank'] <= df['meta']]
    if inplan.empty:
        return {}
    return inplan.groupby(['ISID', 'ym'])['mdm'].nunique().to_dict()


def calcular_series_consultor(df_visitas, df_ausencia_dia, universo, cob_dict=None):
    """
    Série mensal por consultor: visitas, médicos, ausência categorias.
    Lista flat: cada linha = (ISID, ym, ...).
    Só meses fechados.
    """
    rows = []
    isids_univ = list(universo['ISID'])
    cursor = date(2024,1,1)
    while cursor <= MES_FECHADO:
        ano, mes = cursor.year, cursor.month
        ym = f"{ano:04d}-{mes:02d}"
        ini = pd.Timestamp(ano, mes, 1)
        fim = ini + pd.offsets.MonthEnd(0)
        uteis_mes = dias_uteis_mes(ano, mes)

        for isid in isids_univ:
            vis_pm = df_visitas[(df_visitas['ISID']==isid) &
                                (df_visitas['data']>=ini) & (df_visitas['data']<=fim)]
            aus_pm = df_ausencia_dia[(df_ausencia_dia['isid']==isid) &
                                     (df_ausencia_dia['ano']==ano) &
                                     (df_ausencia_dia['mes']==mes)]
            ausencia = aus_pm['fr_total'].sum()
            trab = max(0, uteis_mes - ausencia)
            n_vis = len(vis_pm)
            n_med = vis_pm['mdm'].nunique()
            n_dias = vis_pm['data'].dt.normalize().nunique()
            vd = n_vis / trab if trab > 0 else 0
            freq = n_vis / n_med if n_med > 0 else 0

            # Pular meses sem nada do consultor (não inflar payload)
            if n_vis == 0 and ausencia == 0:
                continue

            rows.append({
                'ISID': isid,
                'ym': ym,
                'visitas': int(n_vis),
                'medicos': int(n_med),
                # Cobertura dentro da frequência planejada (definição global). Subconjunto
                # de 'medicos': exclui re-toques de médicos já satisfeitos em meses anteriores
                # do ciclo. Fallback = n_med quando não há plano carregado (payload antigo).
                'medicos_cob': int(cob_dict.get((isid, ym), 0)) if cob_dict is not None else int(n_med),
                'dias_ativos': int(n_dias),
                'vis_dia': round(vd, 2),
                'freq_medico': round(freq, 2),
                'ausencia': round(ausencia, 2),
                'uteis': int(uteis_mes),
                'trabalhados': round(trab, 2),
                'reunioes': round(aus_pm['fr_reuniao'].sum(), 2),
                'congressos': round(aus_pm['fr_congresso'].sum(), 2),
                'viagem': round(aus_pm['fr_viagem'].sum(), 2),
                'treinamento': round(aus_pm['fr_treinamento'].sum(), 2),
                'gestao': round(aus_pm['fr_gestao'].sum(), 2),
                'pessoais': round(aus_pm['fr_pessoal'].sum(), 2),
            })

        if mes == 12:
            cursor = date(ano+1, 1, 1)
        else:
            cursor = date(ano, mes+1, 1)

    # Filtrar linhas sem atividade — se consultor não tem visitas nem ausência num mês,
    # provavelmente é mês sem dado carregado (não vale a pena ter zero no payload).
    rows = [r for r in rows if (r.get('visitas', 0) > 0 or r.get('ausencia', 0) > 0)]
    return rows


# ============================================================================
# 7B. ANÁLISE DE SETOR — Brickagem alocado × Visitado + vis/dia por UF
# ============================================================================
def analisar_setor_consultor(df_metr, df_visitas, df_dia_aus,
                             path_brickagem=None):
    """
    Para cada consultor produz uma estrutura rica para a aba 'Setor':
      - cidades_alocadas_n   : cidades da brickagem do SA do consultor
      - cidades_visitadas_n  : cidades que ele realmente visitou no MAT
      - cidades_nao_visitadas: alocadas mas sem visita nos últimos 12m
      - pct_cobertura_cidades: visitadas / alocadas
      - ufs_alocadas_n       : UFs da brickagem
      - uf_sede              : UF da brickagem com mais cidades alocadas
      - pct_visitas_uf_sede  : % visitas dentro da UF sede
      - pct_visitas_fora_uf  : 100 - pct_visitas_uf_sede
      - performance_por_uf   : list [{uf, visitas, dias_ativos, vis_dia, n_medicos}]
      - flag_brickagem_sub   : True se cobriu <60% das cidades alocadas
      - flag_ausencia_subreportada: True se (uteis - aus - dias_ativos) > 30 dias no MAT
                              (sugere consultor que não está lançando ausências)

    Tudo aparece como dicionário `setor_analise` injetado em cada consultor.
    """
    # 1) Brickagem por SA -> cidades alocadas
    # NOTA: Geography City fica vazio no nosso brickagem.
    # A informação real está em Geography Geography Description (formato:
    #   "CIDADE-LOGRADOURO - codigo" → cidade = parte antes do primeiro hífen).
    # Geography State também fica vazio, então UF vem do derivar_uf(cidade).
    sa_to_cidades = {}    # sales_area_code -> set(cidades)
    sa_to_ufs = {}        # sales_area_code -> set(ufs)
    sa_to_uf_sede = {}    # sales_area_code -> UF com mais cidades alocadas
    if path_brickagem is None:
        path_brickagem = IN('relatorio_brickagem.csv')
    if os.path.exists(path_brickagem):
        df_br = pd.read_csv(path_brickagem, sep=';', encoding='utf-8', dtype=str)
        df_br.columns = [c.strip() for c in df_br.columns]

        def _parse_cidade(desc):
            if pd.isna(desc) or not desc: return None
            s = str(desc).strip()
            # Remove código no fim "...- 12345"
            s = re.sub(r'\s*-\s*\d+\s*$', '', s)
            # Primeira parte antes do hífen é a cidade
            parts = s.split('-')
            cidade = parts[0].strip() if parts else None
            if not cidade or cidade.upper() in ('', 'NAN', 'NONE'): return None
            # Normalizar acentos pra match com call_city normalizada
            import unicodedata
            t = unicodedata.normalize('NFD', cidade).encode('ascii','ignore').decode('ascii')
            return t.upper().strip()

        df_br['cid'] = df_br['Geography Geography Description'].map(_parse_cidade)
        df_br['uf'] = df_br['cid'].map(derivar_uf)
        df_br = df_br[df_br['cid'].notna()]

        for sa, grp in df_br.groupby('Sales Area Sales Area Code'):
            cidades = set(grp['cid'].dropna())
            ufs_validas = grp[grp['uf'].notna() & (grp['uf']!='??')]
            ufs = set(ufs_validas['uf'])
            sa_to_cidades[sa] = cidades
            sa_to_ufs[sa] = ufs
            # UF sede = UF que abriga mais cidades distintas alocadas
            uf_counts = ufs_validas.groupby('uf')['cid'].nunique().sort_values(ascending=False)
            if len(uf_counts):
                sa_to_uf_sede[sa] = uf_counts.index[0]

    # 2) Para cada consultor
    rows = []
    for _, c in df_metr.iterrows():
        isid = c['ISID']
        sa = c.get('territorio')
        cidades_aloc = sa_to_cidades.get(sa, set())
        ufs_aloc = sa_to_ufs.get(sa, set())

        # UF/CIDADE SEDE: prioridade absoluta da estrutura (quando preenchida)
        # Quando 'VERIFICAR'/None → status 'em_validacao' (não calculamos % UF sede)
        cidade_sede_estr = c.get('cidade_sede')              # já normalizada (UPPER ASCII)
        uf_sede_estr = c.get('uf_sede_estrutura')             # já normalizada (UPPER)
        sede_status = c.get('cidade_sede_status', 'em_validacao')
        sede_em_validacao = (sede_status != 'ok')

        # UF sede final: ESTRUTURA primeiro. Fallback brickagem só se quiser saber qual seria.
        uf_sede = uf_sede_estr if not sede_em_validacao else None
        cidade_sede = cidade_sede_estr if not sede_em_validacao else None
        # Coerência cidade × UF: se a cidade-sede implica uma UF diferente da cadastrada,
        # confia na cidade (corrige cadastros como Curitiba marcada 'PA' em vez de 'PR').
        if cidade_sede:
            uf_da_cidade = derivar_uf(cidade_sede)
            if uf_da_cidade and uf_da_cidade != '??' and uf_da_cidade != uf_sede:
                print(f"  [UF_SEDE] {c.get('nome','?')}: cadastro={uf_sede} × cidade {cidade_sede}→{uf_da_cidade}. Usando {uf_da_cidade}.")
                uf_sede = uf_da_cidade
        uf_sede_fallback_brickagem = sa_to_uf_sede.get(sa)  # mantém pra referência/debug

         # Visitas do consultor no MAT (normalizar cidade pra match com brickagem)
        vis_p = df_visitas[df_visitas['ISID']==isid].copy()
        pct_cidade_sede = None    # MAT
        pct_cidade_sede_3m = None
        pct_cidade_sede_1m = None
        pct_uf_sede_3m = None
        pct_uf_sede_1m = None
        # NOVO: concentração na CIDADE PRINCIPAL por janela (cidade mais visitada),
        # não na cidade-sede. Ver bloco de cálculo abaixo.
        pct_cidade_principal_3m = None
        pct_cidade_principal_1m = None
        if len(vis_p):
            vis_p['uf'] = vis_p['call_city'].map(derivar_uf)
            def _norm_cid(s):
                if pd.isna(s) or not s: return None
                import unicodedata
                t = unicodedata.normalize('NFD', str(s)).encode('ascii','ignore').decode('ascii')
                return t.upper().strip() or None
            vis_p['cid_norm'] = vis_p['call_city'].map(_norm_cid)
            cidades_vis = set(vis_p['cid_norm'].dropna()) - {'', 'NAN', 'NONE'}
            # MAT
            if uf_sede:
                n_sede = (vis_p['uf']==uf_sede).sum()
                pct_uf_sede = round(100 * n_sede / len(vis_p), 1)
            else:
                pct_uf_sede = None
            if cidade_sede:
                n_cid_sede = (vis_p['cid_norm']==cidade_sede).sum()
                pct_cidade_sede = round(100 * n_cid_sede / len(vis_p), 1)
            # Último quarter fechado + último mês
            mf_ts = pd.Timestamp(MES_FECHADO.year, MES_FECHADO.month, 1) + pd.offsets.MonthEnd(0)
            _q_curr_num_s = (MES_FECHADO.month - 1) // 3 + 1
            _q_curr_ano_s = MES_FECHADO.year
            _q_prev_num_s = _q_curr_num_s - 1
            _q_prev_ano_s = _q_curr_ano_s
            if _q_prev_num_s <= 0:
                _q_prev_num_s = 4
                _q_prev_ano_s -= 1
            _q_prev_mes_ini_s = (_q_prev_num_s - 1) * 3 + 1
            _q_prev_ini_s = pd.Timestamp(_q_prev_ano_s, _q_prev_mes_ini_s, 1)
            _q_prev_fim_s = pd.Timestamp(_q_prev_ano_s, _q_prev_mes_ini_s + 2, 1) + pd.offsets.MonthEnd(0)

            cutoff_1m = mf_ts - pd.Timedelta(days=30)
            vis_3m_loc = vis_p[(vis_p['data'] >= _q_prev_ini_s) & (vis_p['data'] <= _q_prev_fim_s)]
            vis_1m_loc = vis_p[vis_p['data'] >= cutoff_1m]
            if uf_sede and len(vis_3m_loc):
                pct_uf_sede_3m = round(100 * (vis_3m_loc['uf']==uf_sede).sum() / len(vis_3m_loc), 1)
            if uf_sede and len(vis_1m_loc):
                pct_uf_sede_1m = round(100 * (vis_1m_loc['uf']==uf_sede).sum() / len(vis_1m_loc), 1)
            if cidade_sede and len(vis_3m_loc):
                pct_cidade_sede_3m = round(100 * (vis_3m_loc['cid_norm']==cidade_sede).sum() / len(vis_3m_loc), 1)
            if cidade_sede and len(vis_1m_loc):
                pct_cidade_sede_1m = round(100 * (vis_1m_loc['cid_norm']==cidade_sede).sum() / len(vis_1m_loc), 1)

            # ── NOVO: concentração na CIDADE PRINCIPAL por janela ──────────────
            # Em vez de medir a cidade-sede (estrutura/residência), mede o share
            # da cidade nº1 efetivamente visitada na janela. Resolve o falso-
            # disperso de quem reside num município vizinho ao painel: ex. base
            # em Santana de Parnaíba mas ~95% das visitas em São Paulo — a sede
            # zera, mas a concentração real é alta. Mesma definição do campo MAT
            # pct_visitas_cidade_principal (top-1 / total da janela).
            def _pct_cid_pri(sub):
                if not len(sub):
                    return None
                cc = sub['call_city'][sub['call_city'].notna() & (sub['call_city'] != '')]
                if not len(cc):
                    return None
                return round(100 * cc.value_counts().iloc[0] / len(sub), 1)
            pct_cidade_principal_3m = _pct_cid_pri(vis_3m_loc)
            pct_cidade_principal_1m = _pct_cid_pri(vis_1m_loc)

            # Performance por UF
            perf_uf = []
            for uf, grp_uf in vis_p[vis_p['uf'].notna() & (vis_p['uf']!='??')].groupby('uf'):
                dias_ativos = grp_uf['data'].dt.normalize().nunique()
                vis_dia = round(len(grp_uf)/dias_ativos, 2) if dias_ativos else 0
                medicos = grp_uf['mdm'].nunique()
                perf_uf.append({
                    'uf': uf, 'visitas': int(len(grp_uf)),
                    'dias_ativos': int(dias_ativos),
                    'vis_dia': float(vis_dia),
                    'medicos': int(medicos),
                    'is_sede': bool(uf_sede) and (uf == uf_sede),
                })
            perf_uf.sort(key=lambda x: x['visitas'], reverse=True)
        else:
            cidades_vis = set()
            pct_uf_sede = None if sede_em_validacao else 0.0
            perf_uf = []

        cidades_aloc_visitadas = cidades_aloc & cidades_vis
        cidades_nao_visitadas = cidades_aloc - cidades_vis
        pct_cob = round(100*len(cidades_aloc_visitadas)/max(1,len(cidades_aloc)), 1) if cidades_aloc else 0.0

        # Flag brickagem muito ampla pouco coberta: < 10% cobertura E ≥ 100 cidades alocadas
        flag_brick_sub = bool(pct_cob < 10 and len(cidades_aloc) >= 100)
        # Flag atuando fora da UF sede: SÓ vale quando sede está definida na estrutura
        flag_fora_sede = bool(uf_sede and pct_uf_sede is not None and pct_uf_sede < 50)
        # Flag ausência sub-reportada
        uteis_12m = c.get('uteis_12m', 0) or 0
        ausencia_12m = c.get('ausencia_12m', 0) or 0
        dias_ativos_12m = c.get('dias_ativos_12m', 0) or 0
        gap = uteis_12m - ausencia_12m - dias_ativos_12m
        flag_aus_sub = bool(gap > 30)

        rows.append({
            'ISID': isid,
            'cidades_alocadas_n': len(cidades_aloc),
            'cidades_visitadas_n': len(cidades_vis),
            'cidades_alocadas_visitadas_n': len(cidades_aloc_visitadas),
            'cidades_nao_visitadas_n': len(cidades_nao_visitadas),
            'cidades_nao_visitadas_sample': sorted(list(cidades_nao_visitadas))[:8],
            'pct_cobertura_cidades': pct_cob,
            'ufs_alocadas_n': len(ufs_aloc),
            'ufs_alocadas': sorted(list(ufs_aloc)),
            'uf_sede': uf_sede,                              # da estrutura (None se em validação)
            'cidade_sede': cidade_sede,                      # da estrutura (None se em validação)
            'cidade_sede_status': sede_status,               # 'ok' | 'em_validacao'
            'uf_sede_brickagem': uf_sede_fallback_brickagem, # referência: o que a brickagem sugeriria
            'pct_visitas_uf_sede': pct_uf_sede,              # None se em validação
            'pct_visitas_cidade_sede': pct_cidade_sede,
            'pct_visitas_uf_sede_3m': pct_uf_sede_3m,
            'pct_visitas_uf_sede_1m': pct_uf_sede_1m,
            'pct_visitas_cidade_sede_3m': pct_cidade_sede_3m,
            'pct_visitas_cidade_sede_1m': pct_cidade_sede_1m,
            'pct_visitas_cidade_principal_3m': pct_cidade_principal_3m,
            'pct_visitas_cidade_principal_1m': pct_cidade_principal_1m,
            'pct_visitas_fora_uf_sede': (round(100 - pct_uf_sede, 1) if pct_uf_sede is not None else None),
            'performance_por_uf': perf_uf,
            'flag_brickagem_subutilizada': flag_brick_sub,
            'flag_fora_uf_sede': flag_fora_sede,
            'flag_ausencia_subreportada': flag_aus_sub,
            'gap_dias_nao_explicados': int(gap) if gap > 0 else 0,
        })
    return pd.DataFrame(rows)


# ============================================================================
# 8. OVERLAP INTRA-TIME + CROSS-TEAM (médicos compartilhados entre consultores)
# ============================================================================
def calcular_turnover_consultores(df_visitas, universo):
    """
    Onda 6 — Índice de turnover de painel por consultor.

    Para cada mês, calcula o % de médicos NOVOS (não visitados nos 3 meses anteriores).
    Depois tira a média dos últimos 3 meses fechados para virar um indicador estável.

    Por que assim:
      - Painel saudável = mesmos médicos sendo visitados consistentemente (relacionamento).
      - Painel rotativo = a cada mês um conjunto diferente (relacionamento fraco, esforço diluído).
      - Janela de 3 meses pra trás equilibra rigor (1 mês fica volátil) e flexibilidade (12m esconde mudança recente).

    Retorna dict {ISID: {turnover_pct_3m, turnover_flag, turnover_serie, turnover_n_meses}}.
    """
    isids_univ = set(universo['ISID'])
    df = df_visitas[df_visitas['ISID'].isin(isids_univ)].copy()
    df['ym'] = df['data'].dt.strftime('%Y-%m')
    # Agrupar conjunto de MDMs visitados por (consultor, mês)
    agg = (df.groupby(['ISID', 'ym'])['mdm']
             .apply(lambda s: set(str(m) for m in s.dropna()))
             .reset_index())
    result = {}
    for isid, group in agg.groupby('ISID'):
        rows = sorted(group.to_dict('records'), key=lambda r: r['ym'])
        serie = []
        for i, r in enumerate(rows):
            if i < 1:  # primeiro mês não tem com o que comparar
                continue
            mdms_atual = r['mdm']
            if not mdms_atual:
                continue
            # Janela: até 3 meses anteriores
            ini = max(0, i - 6)
            mdms_ant = set()
            for j in range(ini, i):
                mdms_ant |= rows[j]['mdm']
            if not mdms_ant:
                # Não dá pra calcular sem histórico — registra mas marca pct=None
                continue
            novos = mdms_atual - mdms_ant
            pct = (len(novos) / len(mdms_atual)) * 100
            serie.append({
                'ym':        r['ym'],
                'pct_novos': round(pct, 1),
                'novos':     len(novos),
                'total':     len(mdms_atual),
            })
        # Índice principal: média dos últimos 3 meses de pct_novos
        ultimos = serie[-6:] if len(serie) >= 6 else serie
        if ultimos:
            turnover_pct = sum(s['pct_novos'] for s in ultimos) / len(ultimos)
        else:
            turnover_pct = None
        # Classificação (faixas conforme proposta validada)
        if turnover_pct is None:
            flag = 'sem_dado'
        elif turnover_pct < 15:
            flag = 'estavel'
        elif turnover_pct < 30:
            flag = 'equilibrado'
        elif turnover_pct < 50:
            flag = 'rotativo'
        else:
            flag = 'volatil'
        result[isid] = {
            'turnover_pct_3m': round(turnover_pct, 1) if turnover_pct is not None else None,
            'turnover_flag':   flag,
            'turnover_serie':  serie[-6:],   # só últimos 6 meses pro payload não inflar
            'turnover_n_meses': len(serie),
        }
    return result


def calcular_overlap(df_visitas, universo, top_n_pairs=400):
    """
    Para cada par de consultores que tenham médicos em comum:
      - shared: nº de médicos compartilhados (MAT, dedupe MDM)
      - A_total, B_total: painel proxy de A e B (médicos únicos visitados MAT)
      - pct_min: % do menor painel que está compartilhado
      - tipo: 'intra' (mesma SF) ou 'cross-team' (SF diferente)
      - mesmo_dia, gap_3d: análise temporal (par visita mesmo médico em até X dias)
      - visitas_par_total, freq_medio_visitas

    Retorna lista de até top_n_pairs pares ordenados por pct_min DESC.
    """
    # Filtrar para janela MAT
    ini = pd.Timestamp(JANELA_INI)
    fim = pd.Timestamp(JANELA_FIM.year, JANELA_FIM.month,1) + pd.offsets.MonthEnd(0)
    df = df_visitas[(df_visitas['data']>=ini) & (df_visitas['data']<=fim)].copy()

    # Por (ISID, MDM): lista de visitas + datas + sf
    isid_sf = dict(zip(universo['ISID'], universo['sales_force']))
    isid_gd = dict(zip(universo['ISID'], universo['gd_name']))
    isid_nome = dict(zip(universo['ISID'], universo['nome']))

    # Quem visitou cada médico → set de ISIDs
    medico_consultores = df.groupby('mdm')['ISID'].apply(set).to_dict()
    # Painéis por consultor
    paineis = df.groupby('ISID')['mdm'].apply(set).to_dict()

    pares = defaultdict(lambda: {'shared':0, 'mdms':set()})
    for mdm, isids in medico_consultores.items():
        if len(isids) < 2:
            continue
        isids_list = sorted(isids)
        for i in range(len(isids_list)):
            for j in range(i+1, len(isids_list)):
                a, b = isids_list[i], isids_list[j]
                key = (a,b)
                pares[key]['shared'] += 1
                pares[key]['mdms'].add(mdm)

    # Construir lista de pares enriquecida
    out = []
    for (a,b), info in pares.items():
        a_total = len(paineis.get(a, set()))
        b_total = len(paineis.get(b, set()))
        shared = info['shared']
        if min(a_total,b_total) == 0:
            continue
        pct_min = round(100 * shared / min(a_total,b_total), 1)
        a_sf = isid_sf.get(a, '?')
        b_sf = isid_sf.get(b, '?')
        tipo = 'intra' if a_sf == b_sf else 'cross-team'

        # Análise temporal: visitas dos 2 consultores aos mesmos MDMs
        mdms_par = info['mdms']
        vis_par = df[df['mdm'].isin(mdms_par) & df['ISID'].isin([a,b])].copy()
        visitas_par_total = len(vis_par)
        freq_medio = round(visitas_par_total / shared, 2) if shared else 0

        # Por MDM, ver datas dos 2 — agora medindo MÉDICOS DISTINTOS visitados no MESMO DIA
        # (vs antes que contava todos os pares de dia)
        medicos_mesmo_dia = 0  # nº de médicos visitados pelos DOIS no mesmo dia (distintos)
        medicos_7d = 0         # nº de médicos visitados pelos DOIS em até 7 dias
        if visitas_par_total > 0:
            vis_par_g = vis_par.groupby('mdm').agg(
                datas_a=('data', lambda s: list(s[vis_par.loc[s.index,'ISID']==a].dt.normalize())),
                datas_b=('data', lambda s: list(s[vis_par.loc[s.index,'ISID']==b].dt.normalize())),
            )
            for _, r in vis_par_g.iterrows():
                da, db = r['datas_a'], r['datas_b']
                if not da or not db: continue
                set_a = set(da); set_b = set(db)
                if set_a & set_b:
                    medicos_mesmo_dia += 1
                # Em até 7 dias
                has_7d = False
                for x in da:
                    for y in db:
                        if abs((x-y).days) <= 7:
                            has_7d = True; break
                    if has_7d: break
                if has_7d: medicos_7d += 1

        # % de médicos compartilhados visitados no mesmo dia
        pct_mesmo_dia = round(100 * medicos_mesmo_dia / shared, 1) if shared else 0
        pct_7d = round(100 * medicos_7d / shared, 1) if shared else 0

        # Classificação de "andando juntos":
        #   Coordenação suspeita: ≥30% dos médicos compartilhados visitados NO MESMO DIA
        #   Atenção: 10-30% mesmo dia
        #   Distribuídos: <10% mesmo dia (cada um vai em momento diferente — saudável)
        if pct_mesmo_dia >= 30:
            padrao = 'Coordenação suspeita'
        elif pct_mesmo_dia >= 10:
            padrao = 'Atenção'
        else:
            padrao = 'Distribuídos'

        out.append({
            'A': a, 'A_nome': isid_nome.get(a,a), 'A_sf': a_sf, 'A_gd': isid_gd.get(a,'?'),
            'B': b, 'B_nome': isid_nome.get(b,b), 'B_sf': b_sf, 'B_gd': isid_gd.get(b,'?'),
            'tipo': tipo,
            'shared': shared,
            'A_total': a_total,
            'B_total': b_total,
            'pct_min': pct_min,
            # NOVAS métricas (foco em "andando juntos"):
            'medicos_mesmo_dia_n': medicos_mesmo_dia,  # médicos distintos visitados pelos DOIS no MESMO DIA
            'pct_mesmo_dia': pct_mesmo_dia,            # % dos médicos compartilhados
            'medicos_7d_n': medicos_7d,                # médicos visitados em até 7 dias
            'pct_7d': pct_7d,
            'padrao_visita': padrao,                   # 'Coordenação suspeita' | 'Atenção' | 'Distribuídos'
            # Retrocompat (campos antigos)
            'mesmo_dia': medicos_mesmo_dia,            # antes era pares de datas; agora é médicos distintos (mais útil)
            'gap_3d': medicos_7d,                      # idem
            'visitas_par_total': visitas_par_total,
            'freq_medio_visitas': freq_medio,
        })

    out.sort(key=lambda d: (-d['pct_min'], -d['shared']))
    return out[:top_n_pairs]


def consolidar_overlap_consultor(df_metr, pares, df_visitas, universo):
    """
    Adiciona ao df_metr (CORRIGIDO — médicos distintos, não soma de pares):
      - shared_intra  = nº médicos distintos compartilhados com colegas da MESMA SF
      - shared_cross  = nº médicos distintos compartilhados com colegas de OUTRA SF
      - exclusivos    = nº médicos visitados só por este consultor
      - pct_overlap_intra/cross_naoclass = sobre painel_visitado (medicos_visit_12m)

    Bug anterior: somava shared de cada par → mesmo médico contado N vezes se
    overlap com N colegas. Agora reconstruo os SETs de médicos a partir das visitas.
    """
    # Mapas: ISID → set(MDM visitados), ISID → SF
    isid_to_mdm = (df_visitas[df_visitas['ISID'].notna() & df_visitas['mdm'].notna()]
                   .groupby('ISID')['mdm'].apply(lambda s: set(s.astype(str))).to_dict())
    isid_to_sf = dict(zip(universo['ISID'], universo['sales_force']))
    # Para cada ISID alvo, comparar seu set com todos os outros
    rows = []
    for _, c in df_metr.iterrows():
        isid = c['ISID']
        my_mdm = isid_to_mdm.get(isid, set())
        my_sf = isid_to_sf.get(isid, '')
        ptot = len(my_mdm) or 1
        intra_set = set()  # médicos compartilhados intra-SF
        cross_set = set()  # médicos compartilhados cross-SF
        for other_isid, other_mdm in isid_to_mdm.items():
            if other_isid == isid: continue
            inter = my_mdm & other_mdm
            if not inter: continue
            other_sf = isid_to_sf.get(other_isid, '')
            if other_sf == my_sf:
                intra_set |= inter
            else:
                cross_set |= inter
        shared_intra = len(intra_set)
        shared_cross = len(cross_set)
        # Médicos que tanto cross quanto intra contam, mas sem duplicar nas categorias
        # A regra de exclusivos é: nenhum colega visitou
        compartilhados_total = intra_set | cross_set
        exclusivos = max(0, len(my_mdm) - len(compartilhados_total))
        pct_intra = round(100*shared_intra / ptot, 1) if ptot else 0.0
        pct_cross = round(100*shared_cross / ptot, 1) if ptot else 0.0
        rows.append({
            'ISID': isid,
            'shared_intra': shared_intra,
            'pct_overlap_intra': pct_intra,
            'shared_cross_coer': 0,
            'shared_cross_incoer': 0,
            'shared_cross_naoclass': shared_cross,
            'pct_overlap_cross_coer': 0.0,
            'pct_overlap_cross_incoer': 0.0,
            'pct_overlap_cross_naoclass': pct_cross,
            'exclusivos': exclusivos,
            'pct_exclusivos': round(100*exclusivos/ptot, 1) if ptot else 0.0,
        })
    df_ov = pd.DataFrame(rows)
    return df_metr.merge(df_ov, on='ISID', how='left')


# ============================================================================
# 9. AGREGAÇÕES SF e GD (para tabela resumo)
# ============================================================================
def agregar_sf(df_metr):
    rows = []
    for sf, grp in df_metr.groupby('sales_force'):
        rows.append({
            'sales_force': sf,
            'n_consultores': int(len(grp)),
            'n_gd': int(grp['gd_name'].nunique()),
            'painel_medio': round(grp['painel_size'].mean(), 1),
            'painel_mediano': round(grp['painel_size'].median(), 1),
            'vis_dia_media': round(grp['vis_dia_media'].mean(), 2),
            'vis_dia_mediana': round(grp['vis_dia_media'].median(), 2),
            'pct_ausencia_media': round(grp['pct_ausencia'].mean(), 1),
            'pct_ausencia_mediana': round(grp['pct_ausencia'].median(), 1),
            'medicos_unicos_mes_medio': round(grp['medicos_unicos_mes'].mean(), 1),
            'freq_medico_mes_medio': round(grp['freq_medico_mes'].mean(), 2),
            'n_viagem': int((grp['tipo_setor']=='Viagem').sum()),
            'n_misto': int((grp['tipo_setor']=='Misto').sum()),
            'n_local': int((grp['tipo_setor']=='Local').sum()),
        })
    rows.sort(key=lambda r: r['sales_force'])
    return rows


def agregar_gd(df_metr):
    rows = []
    for gd_name, grp in df_metr.groupby('gd_name'):
        gd_code = grp['gd_code'].iloc[0]
        rows.append({
            'gd_code': gd_code,
            'gd_name': gd_name,
            'n_consultores': int(len(grp)),
            'n_sf': int(grp['sales_force'].nunique()),
            'painel_medio': round(grp['painel_size'].mean(), 1),
            'vis_dia_media': round(grp['vis_dia_media'].mean(), 2),
            'pct_ausencia_media': round(grp['pct_ausencia'].mean(), 1),
            'n_viagem': int((grp['tipo_setor']=='Viagem').sum()),
            'n_misto': int((grp['tipo_setor']=='Misto').sum()),
            'n_local': int((grp['tipo_setor']=='Local').sum()),
        })
    rows.sort(key=lambda r: r['gd_name'])
    return rows


# ============================================================================
# 10. KPIs CONSOLIDADOS DO TIME
# ============================================================================
def calcular_kpis(df_metr, df_visitas, series):
    """
    KPIs globais para os cards da Visão Geral.
    Inclui as 3 versões de médicos únicos que a Raissa pediu:
      - painel_total_time (dedupe global de médicos visitados nos 90 dias)
      - medicos_unicos_mes_time (média mensal de médicos únicos do time, dedupe global)
      - medicos_unicos_mes_consultor_medio (média/mediana dos consultores)
    """
    # Painel total time: último mês fechado, dedupe global
    if series and series['painel']:
        painel_total_time = series['painel'][-1]['painel_total_time']
    else:
        painel_total_time = 0

    # Média/mediana mensal de medicos únicos por consultor
    medicos_unicos_mes_medio = round(df_metr['medicos_unicos_mes'].mean(), 1)
    medicos_unicos_mes_mediano = round(df_metr['medicos_unicos_mes'].median(), 1)

    # Médicos únicos visitados/mês no TIME (dedupe global)
    n_meses = len(series['visitas']) if series else 1
    medicos_unicos_mes_time_medio = round(
        sum(s['medicos_unicos_time'] for s in series['visitas']) / max(1,n_meses), 1
    )

    # MCCP agregado time
    df_mccp_q = df_metr[df_metr.get('mccp_q_disponivel', False).fillna(False) if 'mccp_q_disponivel' in df_metr.columns else df_metr.index>=0]
    if 'mccp_q_disponivel' in df_metr.columns:
        df_mccp_q = df_metr[df_metr['mccp_q_disponivel']==True]
    else:
        df_mccp_q = df_metr

    total_target_q = df_mccp_q['mccp_target_tri'].sum() if 'mccp_target_tri' in df_mccp_q.columns else 0
    total_real_q = df_mccp_q['mccp_realizado'].sum() if 'mccp_realizado' in df_mccp_q.columns else 0
    total_panel_q = df_mccp_q['mccp_panel'].sum() if 'mccp_panel' in df_mccp_q.columns else 0
    mccp_pct_team = round(total_real_q / total_target_q * 100, 1) if total_target_q else 0
    mccp_freq_team = round(total_target_q / total_panel_q, 2) if total_panel_q else 0
    total_ciclo = df_mccp_q['visitas_ciclo_total'].sum() if 'visitas_ciclo_total' in df_mccp_q.columns else 0
    total_dentro = df_mccp_q['visitas_dentro_mccp'].sum() if 'visitas_dentro_mccp' in df_mccp_q.columns else 0
    pct_dentro_team = round(total_dentro / total_ciclo * 100, 1) if total_ciclo else 0

    return {
        'n_consultores': int(len(df_metr)),
        'n_gd': int(df_metr['gd_name'].nunique()),
        'n_sf': int(df_metr['sales_force'].nunique()),
        # Painel
        'painel_total_time': int(painel_total_time),
        'painel_medio': round(df_metr['painel_size'].mean(),1),
        'painel_mediano': round(df_metr['painel_size'].median(),0),
        'painel_min': int(df_metr['painel_size'].min()),
        'painel_max': int(df_metr['painel_size'].max()),
        # Visitas/dia
        'vis_dia_media': round(df_metr['vis_dia_media'].mean(),2),
        'vis_dia_mediana': round(df_metr['vis_dia_media'].median(),2),
        'vis_dia_min': round(df_metr['vis_dia_media'].min(),2),
        'vis_dia_max': round(df_metr['vis_dia_media'].max(),2),
        # Médicos únicos (3+ versões — chave para o storytelling)
        'medicos_unicos_mes_time': int(medicos_unicos_mes_time_medio),
        'medicos_unicos_mes_consultor_medio': medicos_unicos_mes_medio,
        'medicos_unicos_mes_consultor_mediano': medicos_unicos_mes_mediano,
        'medicos_unicos_mes_taxa_medio': round(df_metr['medicos_unicos_mes_taxa'].mean(), 1),
        'medicos_unicos_mes_taxa_mediano': round(df_metr['medicos_unicos_mes_taxa'].median(), 1),
        'medicos_unicos_mes_medio': round(df_metr['medicos_unicos_mes_taxa'].mean(), 1),
        'freq_medico_mes_medio': round(df_metr['freq_medico_mes'].mean(),2),
        'vis_total_12m': int(df_metr['visitas_12m'].sum()),
        # MCCP agregado (Q corrente)
        'mccp_consultores_com_dado_q': int(len(df_mccp_q)),
        'mccp_target_total_q': int(total_target_q),
        'mccp_realizado_total_q': int(total_real_q),
        'mccp_panel_total_q': int(total_panel_q),
        'mccp_pct_cumprido_team': mccp_pct_team,
        'mccp_freq_media_tri_team': mccp_freq_team,
        'pct_dentro_mccp_team': pct_dentro_team,
        # Ausência
        'pct_ausencia_media': round(df_metr['pct_ausencia'].mean(),1),
        'pct_ausencia_mediana': round(df_metr['pct_ausencia'].median(),1),
        'dias_trabalhados_mes_medio': round(df_metr['trabalhados_mes'].mean(),1),
        # Tipo setor
        'n_viagem': int((df_metr['tipo_setor']=='Viagem').sum()),
        'n_misto': int((df_metr['tipo_setor']=='Misto').sum()),
        'n_local': int((df_metr['tipo_setor']=='Local').sum()),
        # Tempo no setor
        'meses_setor_mediano': float(df_metr['meses_no_setor'].median()) if df_metr['meses_no_setor'].notna().any() else None,
        # Overlap (médio)
        'overlap_intra_medio': round(df_metr['pct_overlap_intra'].mean(),1) if 'pct_overlap_intra' in df_metr.columns else 0,
        # Snapshot/janelas
        'snapshot_painel': MES_FECHADO.strftime('%Y-%m-%d'),
        'janela_ini': JANELA_INI.strftime('%Y-%m-%d'),
        'janela_fim': JANELA_FIM.strftime('%Y-%m-%d'),
        'janela_label': f'MAT {["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"][JANELA_FIM.month-1]}/{str(JANELA_FIM.year)[2:]}',
        'meta_painel': META_PAINEL_DEFAULT,
        'meta_visitas_dia': META_VIS_DIA_DEFAULT,
        'dias_uteis_ano_farma': DIAS_UTEIS_ANO_FARMA,
        'ano_fim_farma': ANO_FIM_FARMA,
    }


# ============================================================================
# 11. MCCP — leitura do relatorio_mccp.csv (substitui leitura do payload antigo)
# ============================================================================
QUARTER_CORRENTE = None  # será setado em main() com base em MES_FECHADO


def _parse_ciclo_mccp(s):
    """
    Parser do campo 'Plano de ciclo: Plano de ciclo multicanal'.
    Formato: MCC-BR-{ano}-{Q}_{sales_area_code}_{ISID}
    Ex: MCC-BR-2026-Q2_BR_U1B02_AZARPE
    """
    m = re.match(r'MCC-BR-(\d{4})-(Q\d)_(.+)_([A-Z0-9]+)$', str(s))
    if m:
        return m.group(1), m.group(2), m.group(3), m.group(4)
    return None, None, None, None


def _quarter_de_mes(mes):
    """Retorna número do quarter (1..4) para um mês 1..12."""
    return (mes - 1) // 3 + 1


def ler_mccp(path=None, universo_isids=None):
    """
    Lê o relatório MCCP, parseia o ciclo, filtra F2F + universo.
    Retorna 2 estruturas:
      - mccp_historico: lista [{ISID, ciclo, target_tri, realizado, panel, pct_cumprido, freq_tri}, ...]
                        cobrindo TODOS os quarters disponíveis (referência de aderência histórica)
      - mccp_corrente: dict {ISID: {panel, target_tri, realizado, remanescente, pct_cumprido, freq_tri, sales_area, n_medicos}}
                       apenas o quarter atual (Q de MES_FECHADO)
    """
    if path is None:
        path = IN('relatorio_mccp.csv')
    if not os.path.exists(path):
        print(f"    AVISO: {path} não encontrado — MCCP ficará vazio")
        return [], {}

    df = pd.read_csv(path, sep=';', encoding='latin-1', dtype=str)
    df.columns = [c.strip() for c in df.columns]
    n0 = len(df)

    # Parser do ciclo
    parsed = df.iloc[:,0].apply(lambda x: pd.Series(_parse_ciclo_mccp(x)))
    df['ano_mccp'] = parsed[0]
    df['q_mccp'] = parsed[1]
    df['sa_mccp'] = parsed[2]
    df['isid_mccp'] = parsed[3]

    # ISID coluna pode estar levemente diferente do parseado; uso ISID coluna (mais confiável)
    df['ISID'] = df['ISID'].astype(str).str.upper().str.strip()

    # Filtros: F2F + universo (se passado)
    df = df[df['Canal']=='Face to Face']
    if universo_isids is not None:
        df = df[df['ISID'].isin(universo_isids)]
    print(f"    MCCP filtrado (F2F + universo): {len(df)}/{n0} linhas")

    # Converter colunas numéricas
    for col in ['Interações do canal - meta','Interações do canal - reais',
                'Interações do canal - remanescentes','meta fatorada mensal',
                'Percentual cumprido do canal','Interações do canal - máx.']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '.'),
                errors='coerce'
            ).fillna(0)

    # Quarter corrente — definido em main()
    q_atual = QUARTER_CORRENTE  # ex: ('2026','Q2')
    print(f"    Quarter corrente: {q_atual}")

    # === Agregação por (ISID, ano-quarter) ===
    df['ciclo'] = df['ano_mccp'] + '-' + df['q_mccp']
    
    # MDMs com meta por (ISID, ciclo)
    mdms_meta_map = df[df['Interações do canal - meta'] > 0].groupby(['ISID', 'ciclo'])['ACC MDM ID'].apply(list).to_dict()

    grp = df.groupby(['ISID','ciclo','sa_mccp']).agg(
        n_medicos=('ACC MDM ID','nunique'),
        target_tri=('Interações do canal - meta','sum'),
        realizado=('Interações do canal - reais','sum'),
        remanescente=('Interações do canal - remanescentes','sum'),
    ).reset_index()
    grp['pct_cumprido'] = (grp['realizado'] / grp['target_tri'] * 100).where(grp['target_tri']>0, 0).round(1)
    grp['freq_tri'] = (grp['target_tri'] / grp['n_medicos']).where(grp['n_medicos']>0, 0).round(2)

    # === Histórico (todos os quarters) ===
    mccp_historico = []
    for _, r in grp.iterrows():
        mccp_historico.append({
            'ISID': r['ISID'],
            'ciclo': r['ciclo'],
            'sales_area': r['sa_mccp'],
            'panel': int(r['n_medicos']),       # nº médicos no plano daquele quarter
            'target_tri': int(r['target_tri']),
            'realizado': int(r['realizado']),
            'remanescente': int(r['remanescente']),
            'pct_cumprido': float(r['pct_cumprido']),
            'freq_tri': float(r['freq_tri']),
            'mdms_meta': mdms_meta_map.get((r['ISID'], r['ciclo']), []),
        })

    # === Corrente (Q da janela) ===
    mccp_corrente = {}
    if q_atual:
        ciclo_corrente = f"{q_atual[0]}-{q_atual[1]}"
        for r in mccp_historico:
            if r['ciclo'] == ciclo_corrente:
                mccp_corrente[r['ISID']] = r

    print(f"    mccp_historico: {len(mccp_historico)} linhas ({grp['ISID'].nunique()} ISIDs × quarters)")
    print(f"    mccp_corrente ({ciclo_corrente if q_atual else '?'}): {len(mccp_corrente)} consultores")

    return mccp_historico, mccp_corrente


def enriquecer_mccp_consultor(df_metr, mccp_corrente, mccp_historico=None):
    """Adiciona ao df_metr campos do MCCP do quarter corrente.
    Também flag mccp_q_disponivel + ultimo_ciclo_mccp para casos sem Q corrente."""
    # Mapa ISID -> último ciclo disponível (pra casos sem Q corrente)
    ultimo_ciclo = {}
    if mccp_historico:
        df_h = pd.DataFrame(mccp_historico).sort_values('ciclo')
        for isid, grp in df_h.groupby('ISID'):
            ultimo_ciclo[isid] = grp.iloc[-1]['ciclo']

    rows = []
    for _, c in df_metr.iterrows():
        isid = c['ISID']
        info = mccp_corrente.get(isid, {})
        target_tri = info.get('target_tri', 0)
        realizado = info.get('realizado', 0)
        remanescente = info.get('remanescente', 0)
        panel = info.get('panel', 0)
        pct = info.get('pct_cumprido', 0)
        freq_tri = info.get('freq_tri', 0)

        rows.append({
            'ISID': isid,
            'mccp_panel': panel,
            'mccp_target_tri': int(target_tri),
            'mccp_realizado': int(realizado),
            'mccp_remanescente': int(remanescente),
            'mccp_pct_cumprido': float(pct),
            'mccp_freq_media_tri': float(freq_tri),
            'mccp_freq_anual': round(freq_tri * 4, 2),
            'mccp_target_mes': round(target_tri / 3, 1),
            'ciclo': info.get('ciclo'),
            'mccp_sales_area': info.get('sales_area'),
            'mccp_q_disponivel': bool(info),  # True se tem dado no Q corrente
            'ultimo_ciclo_mccp': ultimo_ciclo.get(isid),
            'mdms_meta': info.get('mdms_meta', []),
        })
    df_mccp = pd.DataFrame(rows)
    return df_metr.merge(df_mccp, on='ISID', how='left')


def calcular_dentro_fora_mccp(df_visitas, mccp_corrente):
    """
    Pra cada consultor, conta visitas DENTRO do MCCP corrente (médico está no plano F2F do Q atual)
    vs FORA (médico não está no plano).
    Para o Q corrente: olhamos visitas dos meses do Q (Q2 = abr/mai/jun → mas só até MES_FECHADO).
    """
    rows = []
    # MDMs do plano por ISID
    mdms_plano = {}  # ISID -> set(MDMs)

    # Pra recuperar MDMs do plano por consultor preciso ler de novo o MCCP
    # ou passar via mccp_corrente. Como mccp_corrente é só a agregação, vou
    # ler o MCCP de novo aqui — mais simples.
    if os.path.exists(IN('relatorio_mccp.csv')):
        df_m = pd.read_csv(IN('relatorio_mccp.csv'), sep=';', encoding='latin-1', dtype=str)
        df_m.columns = [c.strip() for c in df_m.columns]
        parsed = df_m.iloc[:,0].apply(lambda x: pd.Series(_parse_ciclo_mccp(x)))
        df_m['ano_mccp']=parsed[0]; df_m['q_mccp']=parsed[1]
        if QUARTER_CORRENTE:
            df_m = df_m[(df_m['ano_mccp']==QUARTER_CORRENTE[0]) &
                        (df_m['q_mccp']==QUARTER_CORRENTE[1]) &
                        (df_m['Canal']=='Face to Face')]
        df_m['ISID'] = df_m['ISID'].astype(str).str.upper()
        for isid, grp in df_m.groupby('ISID'):
            mdms_plano[isid] = set(grp['ACC MDM ID'].astype(str))

    # Meses do quarter corrente até MES_FECHADO
    if QUARTER_CORRENTE:
        ano_q = int(QUARTER_CORRENTE[0])
        q_num = int(QUARTER_CORRENTE[1][1])
        mes_ini_q = (q_num - 1) * 3 + 1
        mes_fim_q = mes_ini_q + 2
        ini_q = pd.Timestamp(ano_q, mes_ini_q, 1)
        fim_q = pd.Timestamp(ano_q, mes_fim_q, 1) + pd.offsets.MonthEnd(0)
        # Cap no MES_FECHADO
        fim_q_cap = min(fim_q, pd.Timestamp(MES_FECHADO.year, MES_FECHADO.month, 1) + pd.offsets.MonthEnd(0))
    else:
        ini_q = fim_q_cap = None

    # Pra cada consultor
    out = {}
    for isid in df_visitas['ISID'].dropna().unique():
        mdms_p = mdms_plano.get(isid, set())
        if ini_q is None:
            out[isid] = {'visitas_ciclo_total':0,'visitas_dentro_mccp':0,
                         'visitas_fora_mccp':0,'pct_dentro_mccp':0,'pct_fora_mccp':0,
                         'mdms_dentro_mccp':[], 'mdms_fora_mccp':[]}
            continue
        vis_p = df_visitas[(df_visitas['ISID']==isid) &
                           (df_visitas['data']>=ini_q) &
                           (df_visitas['data']<=fim_q_cap)]
        tot = len(vis_p)
        # Listas (não soma de visitas, mas médicos únicos visitados)
        mdms_visitados = set(vis_p['mdm'].dropna().astype(str))
        mdms_dentro_set = mdms_visitados & mdms_p
        mdms_fora_set = mdms_visitados - mdms_p
        dentro = vis_p['mdm'].isin(mdms_p).sum() if tot > 0 else 0
        fora = tot - dentro
        out[isid] = {
            'visitas_ciclo_total': int(tot),
            'visitas_dentro_mccp': int(dentro),
            'visitas_fora_mccp': int(fora),
            'pct_dentro_mccp': round(100*dentro/tot,1) if tot>0 else 0,
            'pct_fora_mccp': round(100*fora/tot,1) if tot>0 else 0,
            'mdms_dentro_mccp': sorted(list(mdms_dentro_set)),
            'mdms_fora_mccp': sorted(list(mdms_fora_set)),
        }
    return out


def aplicar_dentro_fora_mccp(df_metr, dfo):
    rows = []
    for _, c in df_metr.iterrows():
        isid = c['ISID']
        info = dfo.get(isid, {'visitas_ciclo_total':0,'visitas_dentro_mccp':0,
                              'visitas_fora_mccp':0,'pct_dentro_mccp':0,'pct_fora_mccp':0,
                              'mdms_dentro_mccp':[], 'mdms_fora_mccp':[]})
        rows.append({'ISID': isid, **info})
    return df_metr.merge(pd.DataFrame(rows), on='ISID', how='left')


# ============================================================================
# 11B. PAINEL OFICIAL — leitura do relatorio_painel.csv
# ============================================================================
def ler_painel_oficial(path=None, universo_isids=None,
                        quarters_alvo=None):
    """
    Lê o relatório de painel e retorna 3 estruturas:
      - painel_atual: dict {ISID: {painel_size_oficial, ultimo_snapshot}}  (snapshot mais recente)
      - painel_serie: lista mensal com agregados time
      - painel_por_quarter: dict {ISID: {quarter_label: {mdms, snapshot_used}}}
        Estratégia: snapshot do 2º MÊS do quarter (Q1=fev, Q2=mai, Q3=ago, Q4=nov).
        Se 2º mês não tiver snapshot, cai pro 1º mês. Se nada, cai pro 3º.
    """
    if path is None:
        path = IN('relatorio_painel.csv')
    if not os.path.exists(path):
        print(f"    AVISO: {path} não encontrado — usando proxy 90d para painel")
        return {}, [], {}, {}
    df = pd.read_csv(path, sep=';', encoding='utf-8', dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df['ISID'] = df['ISID CONSULTOR'].astype(str).str.upper()
    df['snap_dt'] = pd.to_datetime(df['SNAPSHOT_DATE_DT'], format='%d/%m/%Y', errors='coerce')
    df['mdm'] = df['MDM CONTA'].astype(str)

    if universo_isids is not None:
        df = df[df['ISID'].isin(universo_isids)]

    # === Painel atual = snapshot mais recente ===
    ultimo_snap = df['snap_dt'].max()
    if pd.notna(ultimo_snap):
        df_ult = df[df['snap_dt']==ultimo_snap]
        # Pré-cálculo: snapshots por consultor (pra flags de qualidade)
        snaps_por_isid = df.groupby('ISID')['snap_dt'].apply(lambda s: sorted(set(s.dropna())))
        # Snapshot mais próximo de 90 dias atrás
        ref_90d_atras = ultimo_snap - pd.Timedelta(days=90)
        painel_atual = {}
        for isid, grp in df_ult.groupby('ISID'):
            mdms = sorted(set(grp['mdm'].dropna().astype(str)))
            # Flag 1: quantos snapshots históricos esse consultor tem?
            snaps_isid = snaps_por_isid.get(isid, [])
            n_snaps = len(snaps_isid)
            # Flag 2: overlap do painel atual com painel de ~90 dias atrás
            # Achar o snapshot mais próximo de 90 dias atrás
            mdms_atual = set(mdms)
            mdms_90d = set()
            snap_90d_use = None
            if len(snaps_isid) >= 2:
                # Pegar snapshot anterior cuja data esteja mais perto de ref_90d_atras
                # mas que seja ANTES do ultimo_snap
                candidatos = [s for s in snaps_isid if s < ultimo_snap]
                if candidatos:
                    # Pegar o mais próximo de 90d atrás (pode ser antes ou depois — o mais perto)
                    snap_90d_use = min(candidatos, key=lambda s: abs((pd.Timestamp(s) - ref_90d_atras).days))
                    df_90d = df[(df['ISID']==isid) & (df['snap_dt']==snap_90d_use)]
                    mdms_90d = set(df_90d['mdm'].dropna().astype(str))
            # Overlap %: quantos médicos do painel atual estavam também 90d atrás
            if mdms_atual and mdms_90d:
                overlap = len(mdms_atual & mdms_90d) / len(mdms_atual) * 100
            else:
                overlap = None  # sem histórico suficiente
            painel_atual[isid] = {
                'painel_size_oficial': len(mdms),
                'mdms_painel': mdms,
                'ultimo_snapshot': ultimo_snap.strftime('%Y-%m-%d'),
                'n_snapshots_historico': n_snaps,
                'painel_overlap_90d_pct': round(overlap, 1) if overlap is not None else None,
                'painel_snapshot_90d_dt': pd.Timestamp(snap_90d_use).strftime('%Y-%m-%d') if snap_90d_use is not None else None,
            }
    else:
        painel_atual = {}

    # === Painel por quarter (snapshot do 2º mês de cada quarter) ===
    painel_por_quarter = {}
    if quarters_alvo and pd.notna(ultimo_snap):
        # snapshots disponíveis por (ano, mês)
        df['ano_snap'] = df['snap_dt'].dt.year
        df['mes_snap'] = df['snap_dt'].dt.month
        snaps_disponiveis = sorted(df['snap_dt'].dropna().unique())
        snaps_por_ano_mes = {}
        for s in snaps_disponiveis:
            ts = pd.Timestamp(s)
            snaps_por_ano_mes[(ts.year, ts.month)] = ts

        for ql in quarters_alvo:
            # ql formato '2026-Q2'
            ano, qstr = ql.split('-')
            ano = int(ano)
            qnum = int(qstr[1])
            mes_ini = (qnum-1)*3 + 1
            # Preferência: 2º mês > 1º mês > 3º mês
            ordem = [mes_ini+1, mes_ini, mes_ini+2]
            snap_use = None
            mes_use = None
            for m in ordem:
                if (ano, m) in snaps_por_ano_mes:
                    snap_use = snaps_por_ano_mes[(ano, m)]
                    mes_use = m
                    break
            if snap_use is None:
                continue
            # Pegar MDMs por consultor naquele snapshot
            df_q = df[df['snap_dt']==snap_use]
            for isid, grp in df_q.groupby('ISID'):
                mdms = sorted(set(grp['mdm'].dropna().astype(str)))
                if isid not in painel_por_quarter:
                    painel_por_quarter[isid] = {}
                painel_por_quarter[isid][ql] = {
                    'mdms': mdms,
                    'size': len(mdms),
                    'snapshot_dt': snap_use.strftime('%Y-%m-%d'),
                    'mes_usado': mes_use,
                }

    # === Série mensal — agregados time ===
    df['ym'] = df['snap_dt'].dt.to_period('M').astype(str)
    serie_rows = []
    for ym, grp in df.groupby('ym'):
        painel_total = grp['mdm'].nunique()
        consultores = grp['ISID'].nunique()
        por_cons = grp.groupby('ISID')['mdm'].nunique()
        serie_rows.append({
            'ym': ym,
            'painel_total_time': int(painel_total),
            'painel_medio_consultor': round(float(por_cons.mean()), 1) if len(por_cons) else 0,
            'painel_mediano_consultor': round(float(por_cons.median()), 1) if len(por_cons) else 0,
            'consultores_no_calc': int(consultores),
            'fonte': 'oficial',
        })
    serie_rows.sort(key=lambda r: r['ym'])

    # === Série mensal POR CONSULTOR — snapshot de painel (MDMs únicos) por mês ===
    # Usado pelo histograma de painel para responder à janela temporal.
    # Formato: {ISID: {ym: painel_size}}  (ym = '2026-04', painel_size = int)
    painel_hist_consultor = {}
    for (ym, isid), grp in df.groupby(['ym', 'ISID']):
        n_mdms = int(grp['mdm'].nunique())
        if isid not in painel_hist_consultor:
            painel_hist_consultor[isid] = {}
        painel_hist_consultor[isid][ym] = n_mdms

    print(f"    Painel oficial: snapshot mais recente {ultimo_snap.date() if pd.notna(ultimo_snap) else '?'} "
          f"({len(painel_atual)} consultores)")
    print(f"    Série painel (oficial): {len(serie_rows)} snapshots mensais")
    print(f"    Série painel por consultor: {len(painel_hist_consultor)} consultores com histórico mensal")
    if painel_por_quarter:
        n_q_total = sum(len(v) for v in painel_por_quarter.values())
        print(f"    Painel por quarter: {len(painel_por_quarter)} consultores × {n_q_total/max(1,len(painel_por_quarter)):.0f} quarters cada (snapshot do 2º mês)")
    return painel_atual, serie_rows, painel_por_quarter, painel_hist_consultor


def aplicar_painel_oficial(df_metr, painel_atual):
    """Substitui painel_size pelo painel oficial mais recente.
    Adiciona também a lista de MDMs do painel + flags de qualidade do histórico.
    Mantém proxy 90d como fallback."""
    novos = []
    snaps = []
    metodos = []
    mdms_painel = []
    n_snaps_hist = []
    overlap_90d = []
    snapshot_90d_dt = []
    for _, c in df_metr.iterrows():
        info = painel_atual.get(c['ISID'])
        if info:
            novos.append(info['painel_size_oficial'])
            snaps.append(info['ultimo_snapshot'])
            metodos.append('oficial')
            mdms_painel.append(info.get('mdms_painel', []))
            n_snaps_hist.append(info.get('n_snapshots_historico', 0))
            overlap_90d.append(info.get('painel_overlap_90d_pct'))
            snapshot_90d_dt.append(info.get('painel_snapshot_90d_dt'))
        else:
            # Sem painel oficial → usa proxy 90d como fallback (tamanho E lista de MDMs).
            # CRÍTICO: se mdms_painel ficar [], 100% das visitas aparecem "fora do painel".
            novos.append(c['painel_size'])
            snaps.append(MES_FECHADO.strftime('%Y-%m-%d'))
            metodos.append(c['painel_proxy_metodo'])
            mdms_painel.append(c.get('mdms_proxy_90d', []) or [])
            n_snaps_hist.append(0)
            overlap_90d.append(None)
            snapshot_90d_dt.append(None)
    df_metr['painel_size'] = novos
    df_metr['snapshot_painel'] = snaps
    df_metr['painel_proxy_metodo'] = metodos
    df_metr['mdms_painel'] = mdms_painel
    df_metr['n_snapshots_historico'] = n_snaps_hist
    df_metr['painel_overlap_90d_pct'] = overlap_90d
    df_metr['painel_snapshot_90d_dt'] = snapshot_90d_dt
    return df_metr


# ============================================================================
# 12. ORQUESTRAÇÃO + MONTAGEM DO PAYLOAD
# ============================================================================
def montar_consultores(df_metr, historico_periodos=None):
    """
    Converte df_metr em lista de dicts (schema compatível com gerar_html.py),
    adicionando os campos NOVOS solicitados.

    PARÂMETRO Onda v9:
      historico_periodos: dict {ISID: [period_atual, period_anterior]} retornado
                          por calcular_historico_periodos(). Só inclui consultores
                          com troca real confirmada (SF ou GD).
    """
    historico_periodos = historico_periodos or {}
    out = []
    for _, c in df_metr.iterrows():
        isid = c['ISID']
        afastado_info = ISIDS_AFASTADOS.get(isid)

        # ICP por janela: critério oficial = MDMs-alvo MCCP cobertos na janela / MDMs-alvo MCCP do painel.
        # F2F e Multi usam a mesma base de visitas F2F disponível no payload atual.
        _mdms_alvo = set(str(x) for x in (c.get('mdmsAlvo') or []) if pd.notna(x))
        _hcps_alvo_total = int(c.get('hcpsAlvoTotal', 0) or len(_mdms_alvo) or 0)

        def _icp_window(_visitados):
            _vis = set(str(x) for x in (_visitados or []) if pd.notna(x))
            _cob = sorted(_vis & _mdms_alvo)
            _pct = round(len(_cob) / _hcps_alvo_total * 100, 1) if _hcps_alvo_total else 0.0
            return len(_cob), _pct, _cob

        _icp_mat_n, _icp_mat_pct, _icp_mat_mdms = _icp_window(c.get('mdms_visitados_mat') or [])
        _icp_3m_n, _icp_3m_pct, _icp_3m_mdms = _icp_window(c.get('mdms_visitados_3m') or [])
        _icp_1m_n, _icp_1m_pct, _icp_1m_mdms = _icp_window(c.get('mdms_visitados_1m') or [])
        _icp_parcial_n, _icp_parcial_pct, _icp_parcial_mdms = _icp_window(c.get('mdms_visitados_parcial') or [])

        # IPA por janela: penetração do painel oficial na base filtrada.
        # Critério: MDMs do painel visitados na janela / MDMs do painel.
        # MAT = 12m; 3m = último quarter/últimos 3 meses; 1m = último mês fechado;
        # parcial = mês atual parcial. Não usar medicos_unicos_mes*12.
        _mdms_painel_ipa = set(str(x) for x in (c.get('mdms_painel') or []) if pd.notna(x))
        _ipa_total = len(_mdms_painel_ipa)

        def _ipa_window(_visitados):
            _vis = set(str(x) for x in (_visitados or []) if pd.notna(x))
            _cob = sorted(_vis & _mdms_painel_ipa)
            _n = len(_cob)
            _pct = round(_n / _ipa_total * 100, 1) if _ipa_total else None
            return _n, _pct, _cob

        _ipa_mat_n, _ipa_mat_pct, _ipa_mat_mdms = _ipa_window(c.get('mdms_visitados_mat') or [])
        _ipa_3m_n, _ipa_3m_pct, _ipa_3m_mdms = _ipa_window(c.get('mdms_visitados_3m') or [])
        _ipa_1m_n, _ipa_1m_pct, _ipa_1m_mdms = _ipa_window(c.get('mdms_visitados_1m') or [])
        _ipa_parcial_n, _ipa_parcial_pct, _ipa_parcial_mdms = _ipa_window(c.get('mdms_visitados_parcial') or [])

        # Compatibilidade com telas antigas: ipa_pct continua representando MAT.
        _ipa_n = _ipa_mat_n
        _ipa_pct = _ipa_mat_pct
        _ipa_cobertos_mdms = _ipa_mat_mdms

        # ICO por janela: cobertura operacional do painel oficial.
        # MAT usa a média mensal já apurada (medicos_unicos_mes_painel), não unique anual/12 bruto.
        def _panel_intersec_n(_visitados):
            _vis = set(str(x) for x in (_visitados or []) if pd.notna(x))
            return len(_vis & _mdms_painel_ipa)

        _painel_size_ico = int(c.get('painel_size', 0) or len(_mdms_painel_ipa) or 0)
        _ico_mat_n = float(c.get('medicos_unicos_mes_painel', 0) or 0)
        _ico_3m_n = _panel_intersec_n(c.get('mdms_visitados_3m') or []) / 3.0
        _ico_1m_n = _panel_intersec_n(c.get('mdms_visitados_1m') or [])
        _ico_parcial_n = _panel_intersec_n(c.get('mdms_visitados_parcial') or [])
        _ico_mat_pct = round(_ico_mat_n / _painel_size_ico * 100, 1) if _painel_size_ico else None
        _ico_3m_pct = round(_ico_3m_n / _painel_size_ico * 100, 1) if _painel_size_ico else None
        _ico_1m_pct = round(_ico_1m_n / _painel_size_ico * 100, 1) if _painel_size_ico else None
        _ico_parcial_pct = round(_ico_parcial_n / _painel_size_ico * 100, 1) if _painel_size_ico else None

        d = {
            # Identificação
            'ISID': isid,
            'nome': c['nome'],
            'sales_force': c['sales_force'],
            'territorio': c['territorio'],
            'win_id': c['win_id'],
            'gd_code': c['gd_code'],
            'gd_name': c['gd_name'],
            'hierarchy': c.get('hierarchy','REP'),

            # FLAGS DE STATUS (NOVO)
            'afastado': afastado_info is not None,
            'afastado_motivo': afastado_info['motivo'] if afastado_info else None,
            'afastado_periodo': afastado_info['periodo'] if afastado_info else None,

            # Tempo no setor (NOVO — antes era null em todos)
            'admissao': c.get('admissao'),
            'meses_no_setor': int(c['meses_no_setor']) if pd.notna(c.get('meses_no_setor')) else None,

            # === Onda v7: troca de Sales Force ===
            # Indicam se este consultor mudou de SF nos últimos 12m e quando.
            # Quando 'trocou_sf_no_mat' = True, o MAT individual está limitado
            # ao período pós-troca (cálculos foram recortados em processar.py).
            'trocou_sf_no_mat': bool(c['trocou_sf_no_mat']) if pd.notna(c.get('trocou_sf_no_mat')) else False,
            'mes_troca_sf': (
                f"{c['mes_troca_sf'][0]}-{c['mes_troca_sf'][1]:02d}"
                if c.get('mes_troca_sf') and isinstance(c.get('mes_troca_sf'), tuple)
                else None
            ),
            'sf_anterior': c.get('sf_anterior') if c.get('sf_anterior') else None,

            # === Onda v8: troca de GD (mesma SF, gestor diferente) ===
            # Quando 'trocou_gd_no_mat' = True, o consultor mudou de gestor + área
            # geográfica nos últimos 12m. MAT também foi recortado.
            'trocou_gd_no_mat': bool(c['trocou_gd_no_mat']) if pd.notna(c.get('trocou_gd_no_mat')) else False,
            'mes_troca_gd': (
                f"{c['mes_troca_gd'][0]}-{c['mes_troca_gd'][1]:02d}"
                if c.get('mes_troca_gd') and isinstance(c.get('mes_troca_gd'), tuple)
                else None
            ),
            'gd_anterior': c.get('gd_anterior') if c.get('gd_anterior') else None,

            # === Onda v9: Histórico comparativo (2 últimos períodos) ===
            # Só preenchido para consultores com troca real confirmada.
            # Permite ver performance antes/depois da troca de SF ou GD.
            'historico_periodos': historico_periodos.get(isid, None),

            # mat_efetivo_meses já foi ajustado em enriquecer_troca_gd para
            # refletir a troca mais recente (SF ou GD).
            'mat_efetivo_meses': int(c['meses_no_setor']) if (
                (
                    (pd.notna(c.get('trocou_sf_no_mat')) and c.get('trocou_sf_no_mat')) or
                    (pd.notna(c.get('trocou_gd_no_mat')) and c.get('trocou_gd_no_mat'))
                )
                and pd.notna(c.get('meses_no_setor'))
            ) else 12,

            # Painel (proxy 90d)
            'painel_size': int(c['painel_size']),
            'painel_mensal': int(c['painel_mes_fechado']),
            'painel_proxy_metodo': c['painel_proxy_metodo'],

            # Janela MAT
            'visitas_12m': int(c['visitas_12m']),
            'medicos_unicos_12m': int(c['medicos_unicos_12m']),
            'medicos_visit_12m': int(c['medicos_unicos_12m']),  # alias compat
            'dias_ativos': int(c['dias_ativos_12m']),
            'meses_ativos': 12,
            'meses_historico': 12,
            'uteis_12m': float(c['uteis_12m']),
            'ausencia_12m': float(c['ausencia_12m']),
            'deslocamento_12m': float(c['viagem_12m']),  # alias compat (era 'deslocamento' antes)
            'viagem_12m': float(c['viagem_12m']),
            'reunioes_12m': float(c['reunioes_12m']),
            'congressos_12m': float(c['congressos_12m']),
            'treinamento_12m': float(c['treinamento_12m']),
            'gestao_12m': float(c['gestao_12m']),
            'pessoais_12m': float(c['pessoais_12m']),
            'trabalhados_12m': float(c['trabalhados_12m']),

            # Médias mensais
            'uteis_mes': float(c['uteis_mes']),
            'ausencia_mes': float(c['ausencia_mes']),
            'deslocamento_mes': float(c['viagem_mes']),  # alias
            'viagem_mes': float(c['viagem_mes']),
            'reunioes_mes': float(c['reunioes_mes']),
            'congressos_mes': float(c['congressos_mes']),
            'treinamento_mes': float(c['treinamento_mes']),
            'gestao_mes': float(c['gestao_mes']),
            'pessoais_mes': float(c['pessoais_mes']),
            'trabalhados_mes': float(c['trabalhados_mes']),
            'dias_trabalhados_mes': float(c['trabalhados_mes']),
            'pct_ausencia': float(c['pct_ausencia']),
            'pct_trabalhados': float(c['pct_trabalhados']),

            # Visitas/dia (CALCULADO CORRETAMENTE: vis / dias_trabalhados)
            'vis_dia_media': float(c['vis_dia_media']),
            'vis_dia_mediana': float(c['vis_dia_mediana']),
            'vis_dia_max': float(c['vis_dia_max']),
            'cv_vis_dia': float(c['cv_vis_dia']),

            # Médicos
            'medicos_unicos_mes': float(c['medicos_unicos_mes']),
            'medicos_unicos_mes_painel': float(c['medicos_unicos_mes_painel']),
            'medicos_unicos_mes_taxa': float(c['medicos_unicos_mes_taxa']),
            'meses_ativos_efetivo': int(c['meses_ativos_efetivo']),
            'freq_medico_mes': float(c['freq_medico_mes']),

            # Geografia (NOVO/ENRIQUECIDO)
            'n_cidades_visitadas': int(c['n_cidades_visitadas']),
            'n_ufs_visitadas': int(c.get('n_ufs_visitadas', 0) or 0),
            'n_ufs_significativas': int(c.get('n_ufs_significativas', 0) or 0),
            'n_ufs_significativas_10pct': int(c.get('n_ufs_significativas_10pct', 0) or 0),
            'pct_visitas_uf_principal': float(c.get('pct_visitas_uf_principal', 0.0) or 0.0),
            'pct_visitas_cidade_principal': float(c.get('pct_visitas_cidade_principal', 0.0) or 0.0),
            'pct_visitas_uf_desconhecida': float(c.get('pct_visitas_uf_desconhecida', 0.0) or 0.0),
            'ufs_top': c.get('ufs_top', {}),
            'cidades_top5': c.get('cidades_top5', {}),
            'tipo_setor': c['tipo_setor'],

            # Análise de Setor (NOVO — brickagem × visitas)
            'cidades_alocadas_n': int(c.get('cidades_alocadas_n', 0) or 0),
            'cidades_visitadas_n': int(c.get('cidades_visitadas_n', 0) or 0),
            'cidades_alocadas_visitadas_n': int(c.get('cidades_alocadas_visitadas_n', 0) or 0),
            'cidades_nao_visitadas_n': int(c.get('cidades_nao_visitadas_n', 0) or 0),
            'cidades_nao_visitadas_sample': c.get('cidades_nao_visitadas_sample', []),
            'pct_cobertura_cidades': float(c.get('pct_cobertura_cidades', 0) or 0),
            'ufs_alocadas_n': int(c.get('ufs_alocadas_n', 0) or 0),
            'ufs_alocadas': c.get('ufs_alocadas', []),
            'uf_sede': (None if c.get('uf_sede') is None or (isinstance(c.get('uf_sede'), float) and pd.isna(c.get('uf_sede'))) else str(c.get('uf_sede'))),
            'cidade_sede': (None if c.get('cidade_sede') is None or (isinstance(c.get('cidade_sede'), float) and pd.isna(c.get('cidade_sede'))) else str(c.get('cidade_sede'))),
            'cidade_sede_status': c.get('cidade_sede_status', 'em_validacao'),
            'uf_sede_brickagem': (None if c.get('uf_sede_brickagem') is None or (isinstance(c.get('uf_sede_brickagem'), float) and pd.isna(c.get('uf_sede_brickagem'))) else str(c.get('uf_sede_brickagem'))),
            'pct_visitas_uf_sede': (None if c.get('pct_visitas_uf_sede') is None
                                    else float(c.get('pct_visitas_uf_sede'))),
            'pct_visitas_cidade_sede': (None if c.get('pct_visitas_cidade_sede') is None
                                        else float(c.get('pct_visitas_cidade_sede'))),
            'pct_visitas_uf_sede_3m': (None if c.get('pct_visitas_uf_sede_3m') is None
                                       else float(c.get('pct_visitas_uf_sede_3m'))),
            'pct_visitas_uf_sede_1m': (None if c.get('pct_visitas_uf_sede_1m') is None
                                       else float(c.get('pct_visitas_uf_sede_1m'))),
            'pct_visitas_cidade_sede_3m': (None if c.get('pct_visitas_cidade_sede_3m') is None
                                           else float(c.get('pct_visitas_cidade_sede_3m'))),
            'pct_visitas_cidade_sede_1m': (None if c.get('pct_visitas_cidade_sede_1m') is None
                                           else float(c.get('pct_visitas_cidade_sede_1m'))),
            'pct_visitas_cidade_principal_3m': (None if c.get('pct_visitas_cidade_principal_3m') is None
                                                else float(c.get('pct_visitas_cidade_principal_3m'))),
            'pct_visitas_cidade_principal_1m': (None if c.get('pct_visitas_cidade_principal_1m') is None
                                                else float(c.get('pct_visitas_cidade_principal_1m'))),
            'pct_visitas_fora_uf_sede': (None if c.get('pct_visitas_fora_uf_sede') is None
                                         else float(c.get('pct_visitas_fora_uf_sede'))),
            'performance_por_uf': c.get('performance_por_uf', []),
            'flag_brickagem_subutilizada': bool(c.get('flag_brickagem_subutilizada', False)),
            'flag_fora_uf_sede': bool(c.get('flag_fora_uf_sede', False)),
            'flag_ausencia_subreportada': bool(c.get('flag_ausencia_subreportada', False)),
            'gap_dias_nao_explicados': int(c.get('gap_dias_nao_explicados', 0) or 0),

            # Tendência
            'slope_vis_dia': float(c['slope_vis_dia']),
            'slope_visitas_mes': 0.0,  # placeholder
            'tendencia_vis_dia': c['tendencia_vis_dia'],

            # Tendência — janela 6m (usada no "Movimento do time")
            'slope_vis_dia_6m': float(c.get('slope_vis_dia_6m', 0) or 0),
            'tendencia_vis_dia_6m': c.get('tendencia_vis_dia_6m', 'Sem dados'),
            'vd_3m_media': float(c.get('vd_3m_media', 0) or 0),
            'vd_6m_media': float(c.get('vd_6m_media', 0) or 0),
            'vd_6m_serie': list(c.get('vd_6m_serie', []) or []),
            # Onda v3 — série de visitas/mês (3-6 pontos) para ICV no html.py
            'visitas_mes_serie': list(c.get('visitas_mes_serie', []) or []),
            'slope_window_n': int(c.get('slope_window_n', 0) or 0),

            # MCCP (preservado do payload antigo nessa rodada)
            'mccp_panel': int(c.get('mccp_panel', 0) or 0),
            'mccp_target_tri': int(c.get('mccp_target_tri', 0) or 0),
            'mccp_realizado': int(c.get('mccp_realizado', 0) or 0),
            'mccp_pct_cumprido': float(c.get('mccp_pct_cumprido', 0) or 0),
            'mccp_freq_media_tri': float(c.get('mccp_freq_media_tri', 0) or 0),
            'mccp_freq_anual': float(c.get('mccp_freq_anual', 0) or 0),
            'mccp_target_mes': round(float(c.get('mccp_target_tri', 0) or 0) / 3, 1),
            'ciclo': c.get('ciclo'),
            'visitas_ciclo_total': int(c.get('visitas_ciclo_total', 0) or 0),
            'visitas_dentro_mccp': int(c.get('visitas_dentro_mccp', 0) or 0),
            'visitas_fora_mccp': int(c.get('visitas_fora_mccp', 0) or 0),
            'pct_dentro_mccp': float(c.get('pct_dentro_mccp', 0) or 0),
            'pct_fora_mccp': float(c.get('pct_fora_mccp', 0) or 0),
            'mdms_dentro_mccp': c.get('mdms_dentro_mccp', []) or [],
            'mdms_fora_mccp': c.get('mdms_fora_mccp', []) or [],
            'mccp_q_disponivel': bool(c.get('mccp_q_disponivel', False)),
            'ultimo_ciclo_mccp': c.get('ultimo_ciclo_mccp'),
            # Motivo legível quando MCCP do Q corrente não está publicado.
            # Encaminhadores e SFs novas geralmente não têm Q corrente publicado pela MSD.
            'mccp_motivo_indisponivel': (
                None if c.get('mccp_q_disponivel', False)
                else (f"MCCP {c.get('ultimo_ciclo_mccp')} é o último ciclo publicado pela MSD para essa SF — Q corrente não disponível"
                      if c.get('ultimo_ciclo_mccp') else
                      "Sem registro de MCCP nesta SF")
            ),

            # Overlap
            'shared_intra': int(c.get('shared_intra', 0) or 0),
            'shared_cross_coer': int(c.get('shared_cross_coer', 0) or 0),
            'shared_cross_incoer': int(c.get('shared_cross_incoer', 0) or 0),
            'shared_cross_naoclass': int(c.get('shared_cross_naoclass', 0) or 0),
            'exclusivos': int(c.get('exclusivos', 0) or 0),
            'pct_overlap_intra': float(c.get('pct_overlap_intra', 0) or 0),
            'pct_overlap_cross_coer': float(c.get('pct_overlap_cross_coer', 0) or 0),
            'pct_overlap_cross_incoer': float(c.get('pct_overlap_cross_incoer', 0) or 0),
            'pct_overlap_cross_naoclass': float(c.get('pct_overlap_cross_naoclass', 0) or 0),
            'pct_exclusivos': float(c.get('pct_exclusivos', 0) or 0),

            # Capacidade (constante)
            'capacidade_dias_ano': round(float(c['trabalhados_mes']) * 12, 1),
            'dias_uteis_ano_farma': DIAS_UTEIS_ANO_FARMA,
            'margem_max_ausencia_pct': round(float(c['pct_ausencia']), 1),
            'snapshot_dt': MES_FECHADO.strftime('%Y-%m-%d'),

            # Localização (placeholders — não temos no dado)
            'uf': None, 'cidade': None,
            # Listas compactas de MDMs (pro JS calcular Total/Dentro/Fora painel reativo)
            'mdms_painel': c.get('mdms_painel', []) or [],
            'mdms_visitados_mat': c.get('mdms_visitados_mat', []) or [],
            # IPA por janela — MDMs do painel tocados na janela / MDMs do painel.
            # Campos sem sufixo mantidos como MAT por compatibilidade.
            'ipa_cobertos_n': _ipa_n,
            'ipa_total_n': _ipa_total,
            'ipa_pct': _ipa_pct,
            'ipa_cobertos_n_mat': _ipa_mat_n,
            'ipa_total_n_mat': _ipa_total,
            'ipa_pct_mat': _ipa_mat_pct,
            'ipa_cobertos_n_3m': _ipa_3m_n,
            'ipa_total_n_3m': _ipa_total,
            'ipa_pct_3m': _ipa_3m_pct,
            'ipa_cobertos_n_1m': _ipa_1m_n,
            'ipa_total_n_1m': _ipa_total,
            'ipa_pct_1m': _ipa_1m_pct,
            'ipa_cobertos_n_parcial': _ipa_parcial_n,
            'ipa_total_n_parcial': _ipa_total,
            'ipa_pct_parcial': _ipa_parcial_pct,

            # ICO por janela — cobertura operacional do painel oficial.
            'cobertura_mensal_pct_mat': _ico_mat_pct,
            'cobertura_mensal_pct_3m': _ico_3m_pct,
            'cobertura_mensal_pct_1m': _ico_1m_pct,
            'cobertura_mensal_pct_parcial': _ico_parcial_pct,
            'ipa_mdms_cobertos': _ipa_cobertos_mdms,
            'ipa_mdms_cobertos_mat': _ipa_mat_mdms,
            'ipa_mdms_cobertos_3m': _ipa_3m_mdms,
            'ipa_mdms_cobertos_1m': _ipa_1m_mdms,
            'ipa_mdms_cobertos_parcial': _ipa_parcial_mdms,
            'mdms_visitados_3m': c.get('mdms_visitados_3m', []) or [],
            'mdms_visitados_1m': c.get('mdms_visitados_1m', []) or [],
            'mdms_visitados_parcial': c.get('mdms_visitados_parcial', []) or [],
            'visitas_3m': int(c.get('visitas_3m', 0) or 0),
            'visitas_1m': int(c.get('visitas_1m', 0) or 0),
            'visitas_parcial': int(c.get('visitas_parcial', 0) or 0),
            'vis_dia_3m': float(c.get('vis_dia_3m', 0) or 0),
            'vis_dia_1m': float(c.get('vis_dia_1m', 0) or 0),
            'vis_dia_parcial': float(c.get('vis_dia_parcial', 0) or 0),
            'pct_ausencia_3m': float(c.get('pct_ausencia_3m', 0) or 0),
            'pct_ausencia_1m': float(c.get('pct_ausencia_1m', 0) or 0),
            'pct_ausencia_parcial': float(c.get('pct_ausencia_parcial', 0) or 0),
            # Ampliação — médias mensais detalhadas por janela (item Filtros de Ausência)
            'uteis_mes_comum_mat':       float(c.get('uteis_mes_comum_mat', c.get('uteis_mes', 0)) or 0),
            'uteis_mes_comum_3m':        float(c.get('uteis_mes_comum_3m', 0) or 0),
            'uteis_mes_comum_1m':        float(c.get('uteis_mes_comum_1m', c.get('uteis_mes_1m', 0)) or 0),
            'uteis_mes_comum_parcial':   float(c.get('uteis_mes_comum_parcial', c.get('parcial_dias_decorridos', 0)) or 0),
            'ausencia_mes_3m':       float(c.get('ausencia_mes_3m', 0) or 0),
            'viagem_mes_3m':         float(c.get('viagem_mes_3m', 0) or 0),
            'reunioes_mes_3m':       float(c.get('reunioes_mes_3m', 0) or 0),
            'congressos_mes_3m':     float(c.get('congressos_mes_3m', 0) or 0),
            'treinamento_mes_3m':    float(c.get('treinamento_mes_3m', 0) or 0),
            'gestao_mes_3m':         float(c.get('gestao_mes_3m', 0) or 0),
            'pessoais_mes_3m':       float(c.get('pessoais_mes_3m', 0) or 0),
            'trabalhados_mes_3m':    float(c.get('trabalhados_mes_3m', 0) or 0),
            'ausencia_mes_1m':       float(c.get('ausencia_mes_1m', 0) or 0),
            'viagem_mes_1m':         float(c.get('viagem_mes_1m', 0) or 0),
            'reunioes_mes_1m':       float(c.get('reunioes_mes_1m', 0) or 0),
            'congressos_mes_1m':     float(c.get('congressos_mes_1m', 0) or 0),
            'treinamento_mes_1m':    float(c.get('treinamento_mes_1m', 0) or 0),
            'gestao_mes_1m':         float(c.get('gestao_mes_1m', 0) or 0),
            'pessoais_mes_1m':       float(c.get('pessoais_mes_1m', 0) or 0),
            'trabalhados_mes_1m':    float(c.get('trabalhados_mes_1m', 0) or 0),
            'ausencia_mes_parcial':       float(c.get('ausencia_mes_parcial', 0) or 0),
            'viagem_mes_parcial':         float(c.get('viagem_mes_parcial', 0) or 0),
            'reunioes_mes_parcial':       float(c.get('reunioes_mes_parcial', 0) or 0),
            'congressos_mes_parcial':     float(c.get('congressos_mes_parcial', 0) or 0),
            'treinamento_mes_parcial':    float(c.get('treinamento_mes_parcial', 0) or 0),
            'gestao_mes_parcial':         float(c.get('gestao_mes_parcial', 0) or 0),
            'pessoais_mes_parcial':       float(c.get('pessoais_mes_parcial', 0) or 0),
            'trabalhados_mes_parcial':    float(c.get('trabalhados_mes_parcial', 0) or 0),
            'parcial_dias_decorridos': int(c.get('parcial_dias_decorridos', 0) or 0),
            'parcial_dias_uteis_total': int(c.get('parcial_dias_uteis_total', 0) or 0),
            'parcial_ym': c.get('parcial_ym'),
            'quarters': c.get('quarters', []),
            'freq_dist_n_med_1x': int(c.get('freq_dist_n_med_1x', 0) or 0),
            'freq_dist_n_med_2_3x': int(c.get('freq_dist_n_med_2_3x', 0) or 0),
            'freq_dist_n_med_4_6x': int(c.get('freq_dist_n_med_4_6x', 0) or 0),
            'freq_dist_n_med_7p': int(c.get('freq_dist_n_med_7p', 0) or 0),
            # Qualidade do painel histórico
            'n_snapshots_historico': int(c.get('n_snapshots_historico') or 0),
            'painel_overlap_90d_pct': (c.get('painel_overlap_90d_pct') if c.get('painel_overlap_90d_pct') is not None else None),
            'painel_snapshot_90d_dt': c.get('painel_snapshot_90d_dt'),
            # Turnover de painel (Onda 6)
            'turnover_pct_3m':   (float(c['turnover_pct_3m']) if c.get('turnover_pct_3m') is not None else None),
            'turnover_flag':     c.get('turnover_flag') or 'sem_dado',
            'turnover_serie':    list(c.get('turnover_serie') or []),
            'turnover_n_meses':  int(c.get('turnover_n_meses') or 0),
            # ── Cobertura de Painel (ICP-F2F · ICP-Multi) ─────────────────────────────
            'hcpsAlvoTotal':       _hcps_alvo_total,
            # Compatibilidade: campos antigos passam a representar MAT pelo mesmo critério de janela.
            'hcpsCobertosF2F':     _icp_mat_n,
            'hcpsCobertosMulti':   _icp_mat_n,
            'pctCoberturaF2F':     _icp_mat_pct,
            'pctCoberturaMulti':   _icp_mat_pct,
            'mdmsAlvo':            sorted(_mdms_alvo),
            'mdmsCobertosF2F':     _icp_mat_mdms,
            'mdmsCobertosMulti':   _icp_mat_mdms,

            # ICP por janela: MDMs-alvo MCCP cobertos na janela ÷ MDMs-alvo MCCP do painel.
            'hcpsCobertosF2F_mat':       _icp_mat_n,
            'pctCoberturaF2F_mat':       _icp_mat_pct,
            'mdmsCobertosF2F_mat':       _icp_mat_mdms,
            'hcpsCobertosF2F_3m':        _icp_3m_n,
            'pctCoberturaF2F_3m':        _icp_3m_pct,
            'mdmsCobertosF2F_3m':        _icp_3m_mdms,
            'hcpsCobertosF2F_1m':        _icp_1m_n,
            'pctCoberturaF2F_1m':        _icp_1m_pct,
            'mdmsCobertosF2F_1m':        _icp_1m_mdms,
            'hcpsCobertosF2F_parcial':   _icp_parcial_n,
            'pctCoberturaF2F_parcial':   _icp_parcial_pct,
            'mdmsCobertosF2F_parcial':   _icp_parcial_mdms,

            # Multi usa o mesmo critério/base F2F quando não há separação de canais digitais confiável.
            'hcpsCobertosMulti_mat':     _icp_mat_n,
            'pctCoberturaMulti_mat':     _icp_mat_pct,
            'mdmsCobertosMulti_mat':     _icp_mat_mdms,
            'hcpsCobertosMulti_3m':      _icp_3m_n,
            'pctCoberturaMulti_3m':      _icp_3m_pct,
            'mdmsCobertosMulti_3m':      _icp_3m_mdms,
            'hcpsCobertosMulti_1m':      _icp_1m_n,
            'pctCoberturaMulti_1m':      _icp_1m_pct,
            'mdmsCobertosMulti_1m':      _icp_1m_mdms,
            'hcpsCobertosMulti_parcial': _icp_parcial_n,
            'pctCoberturaMulti_parcial': _icp_parcial_pct,
            'mdmsCobertosMulti_parcial': _icp_parcial_mdms,
            'snapRefCobertura':    c.get('snapRefCobertura'),
            'quarterRefCobertura': c.get('quarterRefCobertura'),
        }
        out.append(d)

    # === Enriquecer com KPIs sintéticos (Onda 5 — IPT + Score Território) ===
    out = _enriquecer_kpis_sinteticos(out)
    return out


# ============================================================================
# KPIs SINTÉTICOS (Onda 5)
# - IPT (Índice de Pressão de Target)
# - Gap de capacidade
# - Eficiência de cobertura
# - Score de Território Saudável (combina overlap, viagem, UF sede, painel)
# Documentação completa: ver glossário do dashboard.
# ============================================================================

# Parâmetros do simulador por arquétipo (alinhados ao Excel Simulacao_Cobertura)
SIM_PARAMS_DEFAULT = {
    'Local':                {'desloc': 0.5,  'visdia': 5, 'noshow': 0.10, 'freq': 1.0, 'alvo': 0.80},
    'Viagem Interna':       {'desloc': 0.75, 'visdia': 5, 'noshow': 0.12, 'freq': 1.0, 'alvo': 0.80},
    'Viagem Interestadual': {'desloc': 1.5,  'visdia': 5, 'noshow': 0.15, 'freq': 1.0, 'alvo': 0.80},
}
# Thresholds de viagem por arquétipo (dias/mês considerados saudáveis)
LIM_VIAGEM = {'Local': 1, 'Viagem Interna': 3, 'Viagem Interestadual': 6}


def _capacidade_mensal_por_perfil(perfil_params):
    """Réplica da lógica do simulador (calcularCapacidadePerfil) — parte mensal."""
    semanas = 4
    dias_uteis_mes = 20
    dias_campo = max(0, dias_uteis_mes - (perfil_params.get('desloc') or 0) * semanas)
    noshow = perfil_params.get('noshow') or 0
    cob = perfil_params.get('alvo') or 0.8
    freq = perfil_params.get('freq') or 1.0
    visdia = perfil_params.get('visdia') or 0
    visitas_brutas = dias_campo * visdia
    capacidade = visitas_brutas * (1 - noshow)
    painel_ideal = capacidade / (freq * cob) if (freq > 0 and cob > 0) else 0
    return {
        'dias_campo': dias_campo,
        'capacidade_efetiva_mes': capacidade,
        'painel_ideal': painel_ideal,
    }


def _score_overlap_intra(pct):
    if pct is None: return None
    if pct <= 5: return 100
    if pct >= 30: return 0
    if pct <= 15: return 100 - ((pct - 5) / 10) * 50      # 100→50
    return 50 - ((pct - 15) / 15) * 50                     # 50→0

def _score_overlap_cross(pct):
    if pct is None: return None
    if pct <= 20: return 100
    if pct >= 60: return 40
    if pct <= 40: return 100 - ((pct - 20) / 20) * 30      # 100→70
    return 70 - ((pct - 40) / 20) * 30                     # 70→40

def _score_viagem(viagem_mes, tipo_setor):
    if viagem_mes is None: return None
    lim = LIM_VIAGEM.get(tipo_setor, 3)
    if viagem_mes <= lim: return 100
    if viagem_mes >= 2 * lim: return 0
    return 100 - ((viagem_mes - lim) / lim) * 100

def _score_uf_sede(pct_uf):
    if pct_uf is None: return None
    if pct_uf >= 70: return 100
    if pct_uf <= 40: return 0
    return ((pct_uf - 40) / 30) * 100

def _score_painel_delta(painel_atual, painel_ideal):
    if not painel_atual or not painel_ideal: return None
    pct_delta = abs(painel_ideal - painel_atual) / painel_atual * 100
    if pct_delta <= 10: return 100
    if pct_delta >= 50: return 0
    if pct_delta <= 30: return 100 - ((pct_delta - 10) / 20) * 30   # 100→70
    return 70 - ((pct_delta - 30) / 20) * 70                         # 70→0


def _enriquecer_kpis_sinteticos(consultores):
    """
    Adiciona em cada consultor:
      - ipt, ipt_flag, gap_capacidade_mes, eficiencia_cobertura
      - score_territorio, score_territorio_status
      - score_componentes (debug — vê de onde vem o score)
    """
    for c in consultores:
        tipo = c.get('tipo_setor') or 'Local'
        perfil = SIM_PARAMS_DEFAULT.get(tipo, SIM_PARAMS_DEFAULT['Local'])
        cap = _capacidade_mensal_por_perfil(perfil)
        capacidade_efetiva = cap['capacidade_efetiva_mes']
        painel_ideal = cap['painel_ideal']

        # ===== IPT =====
        painel_atual = c.get('painel_size') or 0
        freq_alvo = perfil['freq']
        cob_alvo = perfil['alvo']
        visitas_necessarias = painel_atual * freq_alvo * cob_alvo
        ipt = (visitas_necessarias / capacidade_efetiva) if capacidade_efetiva > 0 else None

        if ipt is None:           flag = 'sem_dado'
        elif ipt < 0.85:          flag = 'confortavel'
        elif ipt < 1.00:          flag = 'no_limite'
        elif ipt < 1.15:          flag = 'pressionado'
        else:                     flag = 'inviavel'

        # Gap de capacidade (positivo = sobra; negativo = falta)
        gap_cap = capacidade_efetiva - visitas_necessarias if capacidade_efetiva > 0 else None

        # Eficiência de cobertura: médicos únicos / visitas realizadas no mês
        visdia = c.get('vis_dia_media') or 0
        dias_trab = c.get('dias_trabalhados_mes') or 0
        visitas_real_mes = visdia * dias_trab
        medicos_unicos_mes = c.get('medicos_unicos_mes') or 0
        eficiencia = (medicos_unicos_mes / visitas_real_mes) if visitas_real_mes > 0 else None

        c['ipt'] = round(ipt, 3) if ipt is not None else None
        c['ipt_flag'] = flag
        c['gap_capacidade_mes'] = round(gap_cap, 1) if gap_cap is not None else None
        c['eficiencia_cobertura'] = round(eficiencia, 3) if eficiencia is not None else None
        c['painel_ideal_perfil'] = round(painel_ideal, 0) if painel_ideal else 0
        c['capacidade_efetiva_perfil'] = round(capacidade_efetiva, 1) if capacidade_efetiva else 0

        # ===== Score de Território Saudável =====
        viagem_mes = c.get('viagem_mes') or c.get('deslocamento_mes') or 0
        pct_uf_sede = c.get('pct_visitas_uf_sede')
        s_intra  = _score_overlap_intra(c.get('pct_overlap_intra'))
        s_cross  = _score_overlap_cross(c.get('pct_overlap_cross_coer') or c.get('pct_overlap_cross_naoclass'))
        s_viagem = _score_viagem(viagem_mes, tipo)
        s_uf     = _score_uf_sede(pct_uf_sede)
        s_painel = _score_painel_delta(painel_atual, painel_ideal)

        comps = [
            ('overlap_intra', s_intra,  0.35),
            ('overlap_cross', s_cross,  0.10),
            ('viagem',        s_viagem, 0.20),
            ('uf_sede',       s_uf,     0.15),
            ('painel_delta',  s_painel, 0.20),
        ]
        num = 0.0
        den = 0.0
        for _, s, w in comps:
            if s is not None:
                num += s * w
                den += w
        score = (num / den) if den > 0 else None

        if score is None:                status = 'sem_dado'
        elif score >= 80:                status = 'saudavel'
        elif score >= 60:                status = 'atencao'
        else:                            status = 'critico'

        c['score_territorio'] = round(score, 1) if score is not None else None
        c['score_territorio_status'] = status
        c['score_componentes'] = {
            'overlap_intra': round(s_intra, 1) if s_intra is not None else None,
            'overlap_cross': round(s_cross, 1) if s_cross is not None else None,
            'viagem':        round(s_viagem, 1) if s_viagem is not None else None,
            'uf_sede':       round(s_uf, 1) if s_uf is not None else None,
            'painel_delta':  round(s_painel, 1) if s_painel is not None else None,
        }
    return consultores


def comparar_payload(payload_novo, payload_antigo, log_path):
    """Cross-check entre payloads antigo e novo — KPIs principais."""
    linhas = []
    linhas.append("="*78)
    linhas.append("COMPARAÇÃO PAYLOAD ANTIGO × PAYLOAD NOVO")
    linhas.append("="*78)

    pa = payload_antigo
    pn = payload_novo

    # Universo
    linhas.append("\n[Universo]")
    linhas.append(f"  Consultores: {len(pa.get('consultores',[]))} → {len(pn.get('consultores',[]))} "
                  f"({len(pn['consultores'])-len(pa['consultores']):+d})")
    isids_antigo = set(c['ISID'] for c in pa['consultores'])
    isids_novo = set(c['ISID'] for c in pn['consultores'])
    saidos = isids_antigo - isids_novo
    entraram = isids_novo - isids_antigo
    if saidos:
        linhas.append(f"  ISIDs que saíram ({len(saidos)}): {sorted(saidos)}")
    if entraram:
        linhas.append(f"  ISIDs que entraram ({len(entraram)}): {sorted(entraram)}")

    # KPIs principais
    linhas.append("\n[KPIs do time]")
    k_antigo = pa.get('kpis', {})
    k_novo = pn.get('kpis', {})
    chaves = ['n_consultores','painel_medio','painel_mediano','vis_dia_media',
              'pct_ausencia_media','dias_trabalhados_mes_medio',
              'medicos_unicos_mes_medio','freq_medico_mes_medio','vis_total_12m']
    for k in chaves:
        v_a = k_antigo.get(k, '—')
        v_n = k_novo.get(k, '—')
        if isinstance(v_a,(int,float)) and isinstance(v_n,(int,float)):
            diff = v_n - v_a
            sinal = '+' if diff >= 0 else ''
            linhas.append(f"  {k:35s}  {v_a:>10}  →  {v_n:>10}   ({sinal}{diff:.2f})")
        else:
            linhas.append(f"  {k:35s}  {v_a:>10}  →  {v_n:>10}")

    # Tipo de setor (mudança crítica)
    linhas.append("\n[Tipo de setor — TODOS os consultores]")
    sf_antigo = Counter(c.get('tipo_setor') for c in pa['consultores'])
    sf_novo = Counter(c.get('tipo_setor') for c in pn['consultores'])
    for t in ['Local','Misto','Viagem',None]:
        linhas.append(f"  {str(t):10s}  {sf_antigo.get(t,0):>5}  →  {sf_novo.get(t,0):>5}")

    # Viagem por consultor — soma
    linhas.append("\n[Dados de viagem]")
    via_antigo = sum((c.get('deslocamento_12m') or c.get('viagem_12m') or 0) for c in pa['consultores'])
    via_novo = sum(c.get('viagem_12m',0) for c in pn['consultores'])
    linhas.append(f"  Soma viagem_12m (MAT): {via_antigo:.1f} → {via_novo:.1f} dias")
    linhas.append(f"  (Bug corrigido: coluna estava sendo agregada errado no antigo)")

    # Médicos únicos / mês
    linhas.append("\n[Médicos únicos/mês — 3 versões NOVAS]")
    linhas.append(f"  Painel total time (90d, dedupe global):       {k_novo.get('painel_total_time','—')}")
    linhas.append(f"  Únicos visitados/mês TIME (dedupe global):    {k_novo.get('medicos_unicos_mes_time','—')}")
    linhas.append(f"  Únicos visitados/mês POR CONSULTOR (médio):   {k_novo.get('medicos_unicos_mes_consultor_medio','—')}")
    linhas.append(f"  Únicos visitados/mês POR CONSULTOR (mediano): {k_novo.get('medicos_unicos_mes_consultor_mediano','—')}")

    # Meses no setor (antes era null em todos)
    linhas.append("\n[Tempo no setor]")
    msn_novo = [c.get('meses_no_setor') for c in pn['consultores']]
    msn_validos = [m for m in msn_novo if m is not None]
    linhas.append(f"  Consultores com meses_no_setor populado: {len(msn_validos)}/{len(msn_novo)} "
                  f"(antes: 0/{len(pa['consultores'])})")
    if msn_validos:
        linhas.append(f"  Mediana: {np.median(msn_validos):.0f} meses · Min: {min(msn_validos)} · Max: {max(msn_validos)}")

    saida = '\n'.join(linhas)
    print('\n'+saida)
    with open(log_path,'w',encoding='utf-8') as f:
        f.write(saida)
    return saida


# ============================================================================
# 13. MAIN
# ============================================================================
def _filtrar_medicos_meta(medicos_meta, consultores):
    """
    Filtra o lookup medicos_meta (219k MDMs) para conter apenas os MDMs
    efetivamente referenciados pelo dashboard (painel + visitados em qualquer janela).
    Reduz drasticamente o tamanho do payload (de ~30MB pra ~5MB).
    """
    if not medicos_meta:
        return {}
    mdms_usados = set()
    for c in consultores:
        for key in ('mdms_painel', 'mdms_visitados_mat', 'mdms_visitados_3m',
                    'mdms_visitados_1m', 'mdms_dentro_mccp', 'mdms_fora_mccp'):
            for m in (c.get(key) or []):
                mdms_usados.add(str(m))
        # Também quarters → mdms
        for q in (c.get('quarters') or []):
            for m in (q.get('mdms') or []):
                mdms_usados.add(str(m))
            for m in (q.get('painel_mdms') or []):
                mdms_usados.add(str(m))
    out = {m: medicos_meta[m] for m in mdms_usados if m in medicos_meta}
    print(f"[medicos_meta] {len(out):,} MDMs no dashboard (de {len(medicos_meta):,} totais no relatorio_1030)")
    return out


def _calc_painel_hist_meses():
    """Calcula qual mês de snapshot usar para cada janela do histograma de painel.

    Regras (definidas pelo cliente):
      - MAT 12m: 9º mês da janela (snapshot representativo — contagem real do painel)
      - 3m: mês do meio do trimestre (ex: fev-mar-abr → mar)
      - 1m: último mês fechado (fotografia)
      - parcial: mês corrente
    """
    # Meses do MAT (12 meses fechados)
    meses_mat = []
    m, y = JANELA_INI.month, JANELA_INI.year
    for _ in range(12):
        meses_mat.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1

    # 9º mês = index 8 (0-based)
    mat_mes = meses_mat[8] if len(meses_mat) >= 9 else meses_mat[-1]

    # Último quarter fechado (2º mês do Q anterior ao corrente)
    _q_c = (MES_FECHADO.month - 1) // 3 + 1
    _q_a = MES_FECHADO.year
    _q_p = _q_c - 1
    _q_y = _q_a
    if _q_p <= 0:
        _q_p = 4
        _q_y -= 1
    _q_m2 = (_q_p - 1) * 3 + 2  # 2º mês do quarter anterior
    tres_m_meio = f"{_q_y}-{_q_m2:02d}"


    # Último mês fechado
    um_mes = MES_FECHADO.strftime('%Y-%m')

    # Mês parcial (corrente)
    parcial = MES_PARCIAL.strftime('%Y-%m')

    return {
        'mat': mat_mes,
        '3m': tres_m_meio,
        '1m': um_mes,
        'parcial': parcial,
        'mat_meses': meses_mat,
    }


def main():
    print(f"\n{'='*78}\nprocessar.py  ·  BU={BU_ALVO}  ·  Mês fechado = {MES_FECHADO}\n{'='*78}\n")

    # Setar QUARTER_CORRENTE global (Q de MES_FECHADO)
    global QUARTER_CORRENTE
    QUARTER_CORRENTE = (str(MES_FECHADO.year), f"Q{_quarter_de_mes(MES_FECHADO.month)}")
    print(f"Quarter corrente: {QUARTER_CORRENTE[0]}-{QUARTER_CORRENTE[1]}\n")

    # 1. Estrutura → universo
    univ = carregar_universo()

    # 2. Ausências
    df_aus_bruto = ler_ausencias_bruto()
    df_aus, df_audit = deduplicar_ausencias(df_aus_bruto)
    df_aus_exp, df_dia = expandir_ausencias_em_dias(df_aus, set(univ['ISID']))

    # 3. Visitas
    df_vis_raw = ler_visitas()
    df_vis = visitas_com_isid(df_vis_raw, univ)

    # Mapa win_id → ISID (necessário para calcular_serie_painel_visitas)
    win_isid_map = dict(zip(univ['win_id'].astype(float), univ['ISID']))
    VIS_FILES = [IN('relatorio_visitas_24.csv'),
                 IN('relatorio_visitas_25.csv'),
                 IN('relatorio_visitas_26.csv')]

    # 3.5. Médicos: Nome + CRM do relatorio_1030.csv (fonte oficial)
    medicos_meta = ler_medicos_1030()

    # === Onda v7: ler exceções de trocas de SF (excecoes_trocas_sf.csv) ===
    print(f"[3.5] Carregando excecoes_trocas_sf.csv...")
    excecoes_trocas = ler_excecoes_trocas_sf()

    # === Onda v8: ler exceções de trocas de GD (excecoes_trocas_gd.csv) ===
    print(f"[3.6] Carregando excecoes_trocas_gd.csv...")
    excecoes_trocas_gd = ler_excecoes_trocas_gd()

    # Aplicar renames/fusões no snapshot atual (se houver)
    univ = aplicar_renames_no_snapshot_atual(univ, excecoes_trocas)

    # 4. Métricas por consultor (com recorte de visitas para troca_real SF e GD)
    df_metr, UTEIS_COMUM = calcular_metricas_consultor(univ, df_vis, df_dia,
                                           trocas_csv=excecoes_trocas,
                                           trocas_gd_csv=excecoes_trocas_gd)
    print(f"[4] Métricas por consultor: {len(df_metr)} linhas")

    # 5. Geografia + tipo setor
    df_metr = enriquecer_geo_consultor(df_metr, df_vis)
    df_metr, df_tipo_audit = classificar_tipo_setor_v2(df_metr)
    print(f"[5] Tipo setor: {df_metr['tipo_setor'].value_counts().to_dict()}")

    # 6. Tempo no setor — via histórico de estruturas (v2) + fallback brickagem
    print(f"[6] Calculando meses_no_setor v2 (estruturas históricas MM_AAAA-ESTRUTURA-FV.csv)...")
    historico_estruturas = ler_estruturas_historicas(PASTA_ESTRUTURAS)
    if historico_estruturas:
        # Aplicar renames/fusões no histórico ANTES de detectar quebras (Onda v7)
        historico_estruturas = aplicar_renames_no_historico(historico_estruturas, excecoes_trocas)
        df_metr = calcular_meses_no_setor_v2(df_metr, historico_estruturas, MES_FECHADO,
                                              trocas_csv=excecoes_trocas)
        # Fallback para quem ficou sem dado (wein_id ausente ou não apareceu no histórico)
        sem_dado = df_metr['meses_no_setor'].isna()
        if sem_dado.any():
            print(f"    Fallback brickagem para {sem_dado.sum()} consultores sem histórico...")
            df_fallback = calcular_meses_no_setor(
                df_metr[sem_dado].copy(), IN('relatorio_brickagem.csv'))
            df_metr.loc[sem_dado, 'meses_no_setor'] = df_fallback['meses_no_setor'].values
            df_metr.loc[sem_dado, 'admissao']       = df_fallback.get('admissao', pd.Series([None]*sem_dado.sum())).values
    else:
        print(f"    Histórico não disponível — usando fallback Sales Area Effective Date...")
        df_metr = calcular_meses_no_setor(df_metr, IN('relatorio_brickagem.csv'))

    # === Onda v8: Enriquecer com troca de GD ===
    print(f"[6.5] Enriquecendo com trocas de GD (excecoes_trocas_gd.csv)...")
    df_metr = enriquecer_troca_gd(df_metr, excecoes_trocas_gd, MES_FECHADO)

    # === Onda v9: Histórico comparativo de períodos para consultores que trocaram ===
    print(f"[6.6] Calculando histórico comparativo (2 últimos períodos)...")
    historico_periodos = calcular_historico_periodos(
        df_metr, df_vis, df_dia, excecoes_trocas, excecoes_trocas_gd, MES_FECHADO
    )

    # 7. Séries temporais
    print(f"[7] Calculando séries temporais (jan/24 → {MES_FECHADO.strftime('%m/%Y')})...")
    series_team = calcular_series_team(df_vis, df_dia, univ)
    _meta_mccp_f2f = _carregar_meta_mccp_f2f(IN('relatorio_mccp.csv'), set(univ['ISID']))
    _cob_mensal = marcar_medicos_cob_mensal(df_vis, _meta_mccp_f2f)
    print(f"    cobertura-frequência: plano F2F p/ {len(_meta_mccp_f2f)} pares (ISID,MDM,ciclo) · {len(_cob_mensal)} (ISID,mês) com cobertura no plano")
    series_consultor = calcular_series_consultor(df_vis, df_dia, univ, cob_dict=_cob_mensal)
    print(f"    series_team.visitas: {len(series_team['visitas'])} meses")
    print(f"    series_team.ausencia: {len(series_team['ausencia'])} meses")
    print(f"    series_team.painel: {len(series_team['painel'])} meses (proxy 90d)")
    print(f"    series_consultor: {len(series_consultor)} linhas")

    # 7A. LIMPEZA DE SÉRIES — excluir meses pré-troca de consultores que vieram de SFs excluídas.
    # Consultores que migraram de BR_HEMATO_TRANSPLANTE/BR_ENCAMINHADORES para SFs pan-tumor
    # têm visitas históricas do período em que estavam na SF antiga. Essas visitas inflam
    # contagens e médias do time pan-tumor.
    # Solução:
    #   1. Excluir meses anteriores à troca de series_consultor
    #   2. Recalcular métricas MAT do consultor usando apenas os meses pós-troca
    #   3. Zerar métricas de consultores sem meses válidos pós-troca (blackout total)
    if SFS_EXCLUIDAS:
        _excl_before = {}  # {ISID: 'YYYY-MM'} → só considerar a partir desse mês
        for _, c in df_metr.iterrows():
            sf_ant = c.get('sf_anterior')
            mes_troca = c.get('mes_troca_sf')
            if sf_ant and str(sf_ant) in SFS_EXCLUIDAS and mes_troca:
                if isinstance(mes_troca, tuple):
                    ym_ini = f"{mes_troca[0]:04d}-{mes_troca[1]:02d}"
                else:
                    ym_ini = str(mes_troca)
                _excl_before[c['ISID']] = ym_ini
        if _excl_before:
            print(f"[7A] Blackout: {len(_excl_before)} consultores migrados de SFs excluídas:")
            for isid, ym_ini in _excl_before.items():
                nome = df_metr.loc[df_metr['ISID']==isid, 'nome'].iloc[0] if len(df_metr[df_metr['ISID']==isid]) else isid
                print(f"     {nome} ({isid}): elegível a partir de {ym_ini}")

            # 7A.1 Filtrar series_consultor
            n_antes = len(series_consultor)
            series_consultor = [
                s for s in series_consultor
                if s['ISID'] not in _excl_before or s['ym'] >= _excl_before[s['ISID']]
            ]
            print(f"     series_consultor: {n_antes} → {len(series_consultor)} (removidas {n_antes - len(series_consultor)})")

            # 7A.2 Recalcular métricas MAT por consultor a partir das séries limpas
            _mat_meses = set()
            c_m = JANELA_INI
            while c_m <= JANELA_FIM:
                _mat_meses.add(f"{c_m.year:04d}-{c_m.month:02d}")
                if c_m.month == 12:
                    c_m = date(c_m.year + 1, 1, 1)
                else:
                    c_m = date(c_m.year, c_m.month + 1, 1)

            _sc_by_isid = {}
            for s in series_consultor:
                _sc_by_isid.setdefault(s['ISID'], []).append(s)

            for isid, ym_ini in _excl_before.items():
                idx = df_metr.index[df_metr['ISID'] == isid]
                if len(idx) == 0:
                    continue
                i = idx[0]
                # Meses MAT válidos pós-blackout
                meses_validos = [s for s in _sc_by_isid.get(isid, [])
                                 if s['ym'] in _mat_meses and s['ym'] >= ym_ini]
                n_m = len(meses_validos)
                if n_m == 0:
                    # Blackout total — zerar métricas MAT (só parcial será válido)
                    df_metr.at[i, 'visitas_12m'] = 0
                    df_metr.at[i, 'vis_dia_media'] = None
                    df_metr.at[i, 'dias_ativos_12m'] = 0
                    df_metr.at[i, 'trabalhados_12m'] = 0
                    df_metr.at[i, 'trabalhados_mes'] = 0
                    df_metr.at[i, 'medicos_unicos_12m'] = 0
                    df_metr.at[i, 'mat_efetivo_meses'] = 0
                    nome = df_metr.at[i, 'nome']
                    print(f"     {nome}: blackout total — métricas MAT zeradas")
                else:
                    total_vis = sum(s['visitas'] for s in meses_validos)
                    total_trab = sum(s.get('trabalhados', s.get('dias_ativos', 0)) for s in meses_validos)
                    total_dias = sum(s['dias_ativos'] for s in meses_validos)
                    total_med = sum(s['medicos'] for s in meses_validos)
                    total_aus = sum(s.get('ausencia', 0) for s in meses_validos)
                    total_uteis = sum(s.get('uteis', 0) for s in meses_validos)
                    new_vd = total_vis / total_trab if total_trab > 0 else 0
                    old_vd = df_metr.at[i, 'vis_dia_media']
                    df_metr.at[i, 'visitas_12m'] = total_vis
                    df_metr.at[i, 'vis_dia_media'] = round(new_vd, 2)
                    df_metr.at[i, 'dias_ativos_12m'] = total_dias
                    df_metr.at[i, 'trabalhados_12m'] = total_trab
                    df_metr.at[i, 'trabalhados_mes'] = round(total_trab / n_m, 2)
                    df_metr.at[i, 'medicos_unicos_12m'] = total_med
                    df_metr.at[i, 'mat_efetivo_meses'] = n_m
                    if total_uteis > 0:
                        df_metr.at[i, 'pct_ausencia'] = round(total_aus / total_uteis * 100, 1)
                        df_metr.at[i, 'ausencia_mes'] = round(total_aus / n_m, 2)
                    nome = df_metr.at[i, 'nome']
                    print(f"     {nome}: vis_dia {old_vd} → {round(new_vd,2)} ({n_m} meses efetivos)")

            print(f"     series_team será recalculado em cima dos dados limpos")

    # 7B. Painel oficial → substituir proxy onde houver + painel POR QUARTER (2º mês)
    print(f"[7B] Lendo painel oficial (relatorio_painel.csv) + painel por quarter...")
    # Quarters alvo = mesmos quarters que cada consultor já tem em c.quarters
    quarters_lbl = []
    if len(df_metr) > 0 and df_metr.iloc[0].get('quarters'):
        quarters_lbl = [q['label'] for q in df_metr.iloc[0]['quarters']]
    painel_atual, painel_serie_oficial, painel_por_quarter, painel_hist_consultor = ler_painel_oficial(
        IN('relatorio_painel.csv'), set(univ['ISID']), quarters_alvo=quarters_lbl)
    df_metr = aplicar_painel_oficial(df_metr, painel_atual)
    # 9. MCCP — lendo do CSV (movido pra cá)
    print(f"[9] Lendo MCCP do relatorio_mccp.csv...")
    mccp_hist, mccp_corr = ler_mccp(IN('relatorio_mccp.csv'), set(univ['ISID']))
    # Plugar painel por quarter em cada consultor
    # Plugar painel por quarter em cada consultor
    if painel_por_quarter:
        # Construir mapa (ISID, ciclo_label) → mdms_meta a partir do mccp_historico
        _mdms_meta_por_ciclo = {}  # {(ISID, '2026-Q1'): [mdm1, mdm2, ...]}
        if mccp_hist:
            for r in mccp_hist:
                key = (r['ISID'], r['ciclo'])
                existing = _mdms_meta_por_ciclo.get(key, [])
                existing.extend(r.get('mdms_meta', []))
                _mdms_meta_por_ciclo[key] = existing
            # Deduplicar
            _mdms_meta_por_ciclo = {k: list(set(v)) for k, v in _mdms_meta_por_ciclo.items()}

        novos_quarters = []
        for _, c in df_metr.iterrows():
            isid = c['ISID']
            qs = c.get('quarters') or []
            p_q = painel_por_quarter.get(isid, {})
            qs_enriq = []
            for q in qs:
                ql = q.get('label')  # formato '2026-Q2'
                pinfo = p_q.get(ql, {})

                # mdms_meta DO MESMO QUARTER que o painel_mdms
                # Fallback: se não tem meta desse quarter, usa o corrente
                mdms_meta_q = _mdms_meta_por_ciclo.get((isid, ql), [])
                if not mdms_meta_q:
                    mdms_meta_q = c.get('mdms_meta', []) or []

                qs_enriq.append({
                    **q,
                    'painel_mdms': pinfo.get('mdms', []),
                    'painel_size': pinfo.get('size', 0),
                    'painel_snapshot': pinfo.get('snapshot_dt'),
                    'painel_mes_usado': pinfo.get('mes_usado'),
                    'mdms_meta': mdms_meta_q,  # CORRIGIDO: meta do MESMO quarter
                })
            novos_quarters.append(qs_enriq)
        df_metr['quarters'] = novos_quarters

    # Sobrescrever série de painel pela versão oficial se existir
    if painel_serie_oficial:
        series_team['painel'] = painel_serie_oficial
    # ── [COB] Cobertura de painel (ICP-F2F / ICP-Multi) ──────────────────────
    print("\n[COB] Calculando ICP-F2F / ICP-Multi...")
    df_cob = calcular_cobertura_painel(
        path_painel    = IN('relatorio_painel.csv'),
        path_mccp      = IN('relatorio_mccp.csv'),
        universo_isids = set(df_metr['ISID'].str.upper().str.strip()),
        mesfechado     = MES_FECHADO,
    )
    df_metr = enriquecer_cobertura_global(df_metr, df_cob)

    # ── [ICP Fallback] Se ICP veio zerado, recalcular a partir dos quarters enriquecidos ──
    # Isso cobre o caso em que calcular_cobertura_painel falha (CSVs ausentes ou join vazio)
    _icp_zerado = all(c.get('hcpsAlvoTotal', 0) == 0 for _, c in df_metr.iterrows())
    if _icp_zerado:
        print("[ICP-Fallback] ICP zerado — recalculando a partir dos quarters enriquecidos...")

        # Garante que as colunas de cobertura existam antes de atribuir listas
        # linha a linha no fallback. Sem isso, .at com lista pode quebrar quando
        # a coluna ainda não existe.
        for col in ["mdmsAlvo", "mdmsCobertosF2F", "mdmsCobertosMulti"]:
            if col not in df_metr.columns and f"{col}_x" not in df_metr.columns:
                df_metr[col] = [[] for _ in range(len(df_metr))]

        for col, default in {
            "hcpsAlvoTotal": 0,
            "hcpsCobertosF2F": 0,
            "hcpsCobertosMulti": 0,
            "pctCoberturaF2F": 0.0,
            "pctCoberturaMulti": 0.0,
            "snapRefCobertura": None,
            "quarterRefCobertura": None,
        }.items():
            if col not in df_metr.columns:
                df_metr[col] = default

        _ciclo_ref = f"{QUARTER_CORRENTE[0]}-{QUARTER_CORRENTE[1]}"
        _n_recalc = 0

        for idx, c in df_metr.iterrows():
            qs = c.get('quarters') or []

            q_ref = None
            for q in reversed(qs):
                if q.get('painel_mdms') and len(q['painel_mdms']) > 0:
                    q_ref = q
                    break

            if not q_ref:
                continue

            painel_set = set(q_ref['painel_mdms'])
            visitados_set = set(q_ref.get('mdms', []))
            
            # Correção: O alvo deve ser a interseção entre o painel e os médicos com meta no MCCP
            meta_set = set(q_ref.get('mdms_meta', []))
            alvo_set = painel_set & meta_set if meta_set else painel_set
            
            alvo = len(alvo_set)
            cobertos_f2f = visitados_set & alvo_set

            n_f2f = len(cobertos_f2f)
            pct_f2f = round(n_f2f / alvo * 100, 1) if alvo else 0.0

            df_metr.at[idx, 'hcpsAlvoTotal'] = alvo
            df_metr.at[idx, 'hcpsCobertosF2F'] = n_f2f
            df_metr.at[idx, 'hcpsCobertosMulti'] = n_f2f
            df_metr.at[idx, 'pctCoberturaF2F'] = pct_f2f
            df_metr.at[idx, 'pctCoberturaMulti'] = pct_f2f

            for col_name, val in [
                ('mdmsAlvo', sorted(alvo_set)),
                ('mdmsCobertosF2F', sorted(cobertos_f2f)),
                ('mdmsCobertosMulti', sorted(cobertos_f2f)),
            ]:
                if col_name in df_metr.columns:
                    target_col = col_name
                elif f"{col_name}_x" in df_metr.columns:
                    target_col = f"{col_name}_x"
                elif f"{col_name}_y" in df_metr.columns:
                    target_col = f"{col_name}_y"
                else:
                    df_metr[col_name] = [[] for _ in range(len(df_metr))]
                    target_col = col_name

                df_metr.at[idx, target_col] = val

            df_metr.at[idx, 'snapRefCobertura'] = q_ref.get('painel_snapshot')
            df_metr.at[idx, 'quarterRefCobertura'] = q_ref.get('label')
            _n_recalc += 1

        if _n_recalc:
            _avg_f2f = df_metr['pctCoberturaF2F'].mean()
            print(f"  [ICP-Fallback] {_n_recalc} consultores recalculados | F2F médio={_avg_f2f:.1f}%")
            
    # 8. Overlap
    print(f"[8] Calculando overlap (com dedup correto)...")
    pares = calcular_overlap(df_vis, univ)
    print(f"    {len(pares)} pares retidos (top por pct_min)")
    df_metr = consolidar_overlap_consultor(df_metr, pares, df_vis, univ)

    # 8C. Turnover de painel (Onda 6 — % médicos novos vs 6 meses anteriores)
    print(f"[8C] Calculando turnover de painel...")
    turnover_map = calcular_turnover_consultores(df_vis, univ)
    # Injetar no df_metr (4 colunas por consultor)
    df_metr['turnover_pct_3m']   = df_metr['ISID'].map(lambda i: (turnover_map.get(i) or {}).get('turnover_pct_3m'))
    df_metr['turnover_flag']     = df_metr['ISID'].map(lambda i: (turnover_map.get(i) or {}).get('turnover_flag', 'sem_dado'))
    df_metr['turnover_serie']    = df_metr['ISID'].map(lambda i: (turnover_map.get(i) or {}).get('turnover_serie') or [])
    df_metr['turnover_n_meses']  = df_metr['ISID'].map(lambda i: (turnover_map.get(i) or {}).get('turnover_n_meses', 0))
    from collections import Counter
    dist = Counter(df_metr['turnover_flag'])
    print(f"    Turnover por faixa: {dict(dist)}")

    # 8B. Análise de setor — brickagem alocada × visitada, performance por UF
    print(f"[8B] Análise de Setor (brickagem × visitas reais)...")
    df_setor = analisar_setor_consultor(df_metr, df_vis, df_dia, IN('relatorio_brickagem.csv'))
    # Tirar do df_metr as colunas duplicadas antes do merge (pra não criar _x/_y)
    cols_dup = ['uf_sede','cidade_sede','cidade_sede_status']
    df_metr = df_metr.drop(columns=[c for c in cols_dup if c in df_metr.columns], errors='ignore')
    df_metr = df_metr.merge(df_setor, on='ISID', how='left')
    print(f"    Cobertura média de cidades alocadas: {df_setor['pct_cobertura_cidades'].mean():.1f}%")
    print(f"    Consultores com brickagem subutilizada (<60%): {df_setor['flag_brickagem_subutilizada'].sum()}")
    print(f"    Consultores com ausência possivelmente subreportada: {df_setor['flag_ausencia_subreportada'].sum()}")

    # 8B.1 Série mensal painel×visitas (ICP por mês, dentro/fora do painel)
    print("[8B.1] Calculando série mensal painel×visitas...")
    _serie_pv = []; _serie_pv_time = []
    try:
        _serie_pv = calcular_serie_painel_visitas(
            paths_vis=VIS_FILES, path_painel=IN('relatorio_painel.csv'),
            path_mccp=IN('relatorio_mccp.csv'), win_isid_map=win_isid_map,
            universo_isids=set(df_metr['ISID'].str.upper().str.strip()),
            data_ini=JANELA_INI, data_fim=MES_FECHADO,
        )
        _serie_pv_time = _agregar_serie_pv_time(_serie_pv)
        print(f"    série painel×visitas: {len(_serie_pv)} registros ISID×mês, {len(_serie_pv_time)} meses time")
    except Exception as _e_pv:
        print(f"    [AVISO] série painel×visitas ignorada: {_e_pv}")
    # 9. MCCP — enriquecer consultores (leitura já feita acima no bloco 7B)
    df_metr = enriquecer_mccp_consultor(df_metr, mccp_corr, mccp_hist)
    # 9B. Dentro/fora MCCP (do quarter corrente)
    print(f"[9B] Calculando visitas dentro/fora MCCP ({QUARTER_CORRENTE[0]}-{QUARTER_CORRENTE[1]})...")
    dfo_map = calcular_dentro_fora_mccp(df_vis, mccp_corr)
    df_metr = aplicar_dentro_fora_mccp(df_metr, dfo_map)

    # 9C. Distribuição de frequência MCCP do quarter atual
    freq_dist = {}
    if mccp_hist:
        df_mh = pd.DataFrame(mccp_hist)
        ciclo_corrente = f"{QUARTER_CORRENTE[0]}-{QUARTER_CORRENTE[1]}"
        df_q = df_mh[df_mh['ciclo']==ciclo_corrente]
        # Distribuição de freq_tri (visitas planejadas/médico no Q)
        if len(df_q):
            faixas = {'1x':0,'2x':0,'3x':0,'4x+':0,'<1x':0}
            for _, r in df_q.iterrows():
                f = r['freq_tri']
                if f < 1: faixas['<1x'] += 1
                elif f < 2: faixas['1x'] += 1
                elif f < 3: faixas['2x'] += 1
                elif f < 4: faixas['3x'] += 1
                else: faixas['4x+'] += 1
            freq_dist = faixas

    # 10. KPIs
    kpis = calcular_kpis(df_metr, df_vis, series_team)

    # 11. Agregações SF/GD
    sf_rows = agregar_sf(df_metr)
    gd_rows = agregar_gd(df_metr)

    # 12. Monta lista de consultores no schema final
    consultores = montar_consultores(df_metr, historico_periodos=historico_periodos)

    # 13. Pares
    pares_overlap = pares
    pares_medicos_detail = []

    # 14. Payload final
    payload = {
        'meta': {
            'bu': BU_LABEL,
            'bu_filtro': BU_ALVO,
            'sfs_excluidas': list(SFS_EXCLUIDAS) if SFS_EXCLUIDAS else [],
            'gerado_em': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'snapshot_painel': MES_FECHADO.strftime('%Y-%m-%d 00:00:00'),
            'ciclo_mccp': f"{QUARTER_CORRENTE[0]}-{QUARTER_CORRENTE[1]}",
            'janela_ini': fmt_ym_pt(JANELA_INI.year, JANELA_INI.month),
            'janela_fim': fmt_ym_pt(JANELA_FIM.year, JANELA_FIM.month),
            'janela_label': kpis['janela_label'],
            'meta_painel_default': META_PAINEL_DEFAULT,
            'meta_visitas_dia_default': META_VIS_DIA_DEFAULT,
            'dias_uteis_ano_farma': DIAS_UTEIS_ANO_FARMA,
            'ano_fim_farma': ANO_FIM_FARMA,
            'mes_fechado': MES_FECHADO.strftime('%Y-%m-%d'),
            # Mapeamento janela → mês para histograma de painel
            # MAT: 9º mês da janela (snapshot representativo sem duplicata)
            # 3m: mês do meio do trimestre
            # 1m: último mês fechado
            # parcial: mês corrente
            'painel_hist_meses': _calc_painel_hist_meses(),
            'observacoes': {
                'painel_oficial': f'painel_size = MDMs únicos no relatorio_painel.csv (snapshot mais recente). Fallback: visitas_90d quando consultor não está no painel.',
                'mccp_origem': f'MCCP lido do relatorio_mccp.csv. Filtros: F2F + universo. Quarter corrente: {QUARTER_CORRENTE[0]}-{QUARTER_CORRENTE[1]}. Histórico em mccp_historico.',
                'dedup_regras': 'R0+R1+R2+R3 — chave SEM criado_por (resolve duplicatas Integration User × consultor próprio)',
                'tipo_setor_regra': f'UFs significativas (≥5% volume): ≤1 Local, =2 Misto, ≥3 Viagem',
                'meses_no_setor_origem': 'Sales Area Effective Date (relatorio_brickagem.csv). NÃO é tempo do consultor no SA — é tempo do SA existir.',
                'corte_temporal': f'todas as séries terminam em {MES_FECHADO} (mês fechado)',
                'universo': f'{BU_ALVO} × {HIERARCHY_FILTRO} ({len(consultores)} pessoas)',
            },
            'travel_rules': {
                'max_cidades_local': TIPO_LOCAL_MAX_CIDADES,
                'max_ufs_local': TIPO_LOCAL_MAX_UFS,
                'min_cidades_travel': TIPO_VIAGEM_MIN_CIDADES,
                'min_ufs_travel': TIPO_VIAGEM_MIN_UFS,
            },
            # Denominador comum de dias úteis — calendário, igual para todos.
            # O front deve usar esses valores (não os do consultor individual)
            # como denominador nos gráficos de ausência por arquétipo.
            **UTEIS_COMUM,
        },
        'kpis': kpis,
        'consultores': consultores,
        'sales_forces': sf_rows,
        'gds': gd_rows,
        'pares_overlap': pares_overlap,
        'pares_medicos_detail': pares_medicos_detail,
        'series_team': series_team,
        'series_consultor': series_consultor,
        'mccp_historico': mccp_hist,
        'freq_dist_mccp': freq_dist,
        # Médicos: lookup MDM → {nome, crm, tipo, especialidade}
        # Limitado aos MDMs efetivamente usados no dashboard para reduzir tamanho do payload.
        'medicos_meta': _filtrar_medicos_meta(medicos_meta, consultores),
        # Série mensal de painel por consultor — {ISID: {ym: painel_size}}
        # Usado pelo histograma de painel para responder à janela temporal.
        'painel_hist_consultor': painel_hist_consultor,
        'serie_painel_visitas':      _serie_pv,
        'serie_painel_visitas_time': _serie_pv_time,

    }

    # 15. Salvar — sanitizar NaN/Inf (JSON spec não suporta, mas Python aceita)
    import math
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(sanitize(v) for v in obj)
        if isinstance(obj, (datetime, date)):
            return obj.strftime('%Y-%m-%d')
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        # numpy.float64 NaN também
        try:
            if hasattr(obj, 'item'):
                v = obj.item()
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return None
        except Exception:
            pass
        # pd.isna pra catch tudo (incluindo np.nan, pd.NaT)
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
        return obj
    payload_clean = sanitize(payload)

    with open(OUT('payload.json'),'w',encoding='utf-8') as f:
        json.dump(payload_clean, f, ensure_ascii=False, allow_nan=False, default=str, indent=None)
    sz_mb = os.path.getsize(OUT('payload.json')) / 1024 / 1024
    print(f"\n[10] payload.json salvo em {OUT('payload.json')} ({sz_mb:.1f} MB)")

    # Audits
    df_audit.to_csv(OUT('dedup_audit.csv'), sep=';', index=False, encoding='utf-8-sig')
    print(f"     dedup_audit.csv salvo ({len(df_audit)} linhas)")
    df_tipo_audit.to_csv(OUT('tipo_setor_audit.csv'), sep=';', index=False, encoding='utf-8-sig')
    print(f"     tipo_setor_audit.csv salvo ({len(df_tipo_audit)} linhas)")

    # 16. Comparar com antigo
    try:
        with open(OUT('payload_antigo.json'),'r',encoding='utf-8') as f:
            payload_antigo = json.load(f)
        comparar_payload(payload, payload_antigo, OUT('comparacao_antigo_vs_novo.txt'))
    except Exception as e:
        print(f"\nNão consegui comparar com payload antigo: {e}")

    return payload


if __name__ == '__main__':
    payload = main()
    print(f"\n{'='*78}\nDONE\n{'='*78}\n")
