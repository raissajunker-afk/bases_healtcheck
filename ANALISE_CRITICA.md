# Análise crítica — Portal vs. abas/gráficos novos

## O que já existe no legado (e não deve ser duplicado cegamente)

O `html (13).py` / `gerar_html_legacy.py` já entrega, com alta profundidade:

| Aba legada | Conteúdo denso | Recomendação no portal |
|------------|----------------|------------------------|
| Visão Geral | KPIs time, cards, distribuições | **Migrar** → Executive Overview + Performance |
| Detalhe por Consultor | Tabela wide 50+ colunas, sort, drill | **Manter no legado** — portal mostra tabela resumida + CSV |
| Visitação | Histogramas, séries por consultor | **Portal**: KPIs + ranking + série time; histogramas **só no legado** |
| Índices de Performance | IPT, scores compostos | **Portal**: resumo; detalhe **legado** |
| Histórico de Performance | Séries longas por REP | **Portal**: evolução agregada; histórico REP **legado** |
| Simulador | Metas, cenários, what-if | **Não replicar no portal v1** — `--with-legacy` |
| Ausências | TOT, categorias, dedup | **Portal**: % + série + tabela resumo |
| Deslocamento | UF/cidade, flags | **Portal**: KPIs territoriais |
| Linha do Tempo | Painel × visitas mensal | **Portal**: gráfico barras time |
| Overlap | Pares, drill médicos | **Portal**: top pares + CSV; drill **legado** |
| Glossário | Metodologia longa | **Portal**: bloco metodologia + Governança |

## Onde vale novas “abas” (seções do portal)

| Seção portal | Vale a pena? | Motivo |
|--------------|--------------|--------|
| 1 Executive Overview | **Sim** | Pergunta única da liderança; poucos KPIs |
| 2 Performance Comercial | **Sim** | Dados ricos no payload (`vis_dia`, rankings) |
| 3 Cobertura e Painel | **Sim** | IPA/MCCP já calculados |
| 4 Visitação e Frequência | **Sim** | `series_team`, `freq_dist_mccp` |
| 5 Eficiência Territorial | **Sim** | `tipo_setor`, UF sede, score |
| 6 Ausências e Capacidade | **Sim** | `pct_ausencia`, séries |
| 7 Especialidades × Franquias | **Condicional** | Só com `franquias_especialidades.csv` + extensão `processar.py` |
| 8 Qualidade de Execução | **Sim** | % dentro/fora MCCP |
| 9 Overlap | **Sim** (resumo) | Drill profundo → legado |
| 10 Simulador | **Não no portal** | Lógica interativa pesada → legado |
| 11 Oportunidades | **Sim** | Consolida insights (não recalcula) |
| 12 Governança | **Sim** | Meta, exclusões, auditoria |
| 13 Canal Digital / Multicanal | **Sim (leve)** | Gap F2F vs multi já no payload |
| 14 Benchmarking e Metas | **Sim** | Meta painel/visita vs realizado |
| 15 Relacionamento | **Parcial** | Recorrência via `freq_dist_mccp` |

## Gráficos novos — prioridade

1. **Alta** — Série visitas/ausência time (barras) — já no portal.
2. **Alta** — Rankings consultor (tabela ordenável) — portal + CSV.
3. **Média** — Cobertura F2F por SF/GD — tabelas agregadas.
4. **Baixa** — Heatmap especialidade×franquia — exige processamento novo.
5. **Evitar v1** — Duplicar simulador, histograma painel interativo, curvas IPT 3D.

## Fluxo recomendado no seu PC

```bash
cd C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck
# ou clone do repo com pasta healthcheck/
pip install -r requirements.txt
python main.py
```

Abrir: `Healthcheck_Portal.html` (mesma pasta de saída).

Legado opcional: `python main.py --with-legacy` → `Healthcheck_ONCOLOGIA_PAN-TUMOR.html`

## Critério de sucesso

- Um comando offline gera HTML compartilhável.
- Regras de negócio **somente** em `processar.py` (inalteradas).
- Portal navegável por tema; CSV onde há tabela.
- Legado só quando precisar de simulador/detalhe profundo.
