import streamlit as st
import pandas as pd
import numpy as np

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="CalculaInvest", page_icon="📈", layout="wide")

# --- INJEÇÃO DE CSS (FONTE ELÁSTICA E RESPONSIVA) ---
st.markdown("""
<style>
/* 1. Torna o tamanho da fonte dinâmico (elástico) com base na largura da tela */
[data-testid="stMetricValue"] {
    font-size: clamp(14px, 1.8vw, 30px) !important;
}

/* 2. Destrói a regra nativa do Streamlit que coloca os "..." (reticências) */
[data-testid="stMetricValue"] > div {
    text-overflow: unset !important;
    white-space: normal !important;
    word-wrap: break-word !important;
    overflow: visible !important;
}

/* 3. Aplica a mesma regra anti-corte para as legendas verdes/vermelhas de baixo */
[data-testid="stMetricDelta"] > div {
    white-space: normal !important;
    text-overflow: unset !important;
    overflow: visible !important;
}
</style>
""", unsafe_allow_html=True)

# --- 2. MOTORES DE CÁLCULO (ARQUITETURA MODULAR) ---
def calcular_imposto_renda(lucro_bruto, anos):
    """Calcula o IR com base na tabela regressiva brasileira."""
    if lucro_bruto <= 0: return 0.0
    if anos <= 0.5: return lucro_bruto * 0.225
    elif anos <= 1.0: return lucro_bruto * 0.20
    elif anos <= 2.0: return lucro_bruto * 0.175
    else: return lucro_bruto * 0.15

def calcular_fluxo_renda_fixa(v_inicial, aporte, meses, taxa_anual):
    """Calcula o fluxo de caixa determinístico para Renda Fixa."""
    historico = [v_inicial]
    investido = [v_inicial]
    dt = 1 / 12
    taxa_mensal = (1 + taxa_anual) ** dt - 1
    
    saldo = v_inicial
    bolso = v_inicial
    
    for _ in range(meses):
        saldo += aporte
        bolso += aporte
        saldo += saldo * taxa_mensal
        historico.append(saldo)
        investido.append(bolso)
        
    return np.array(historico), np.array(investido)

def simular_monte_carlo_mbg(v_inicial, aporte, meses, mu, sigma, num_simulacoes=500):
    """Simula múltiplos cenários estocásticos usando NumPy para alta performance."""
    dt = 1 / 12
    cenarios = np.zeros((meses + 1, num_simulacoes))
    cenarios[0] = v_inicial
    
    investido = [v_inicial]
    bolso = v_inicial
    
    for t in range(1, meses + 1):
        bolso += aporte
        investido.append(bolso)
        
        # Gera o choque aleatório para as 500 simulações simultaneamente
        Z = np.random.standard_normal(num_simulacoes)
        fator_crescimento = np.exp((mu - (sigma**2) / 2) * dt + sigma * np.sqrt(dt) * Z)
        
        # Aplica o crescimento ao saldo anterior somado ao aporte
        cenarios[t] = (cenarios[t-1] + aporte) * fator_crescimento
        
    return cenarios, np.array(investido)

# --- 3. BARRA LATERAL (PARÂMETROS DE ENTRADA) ---
st.sidebar.header("⚙️ Parâmetros do Projeto")
# Alterado value para 0.0
valor_inicial = st.sidebar.number_input("Capital Inicial (R$)", value=0.0, step=1000.0)
aporte_mensal = st.sidebar.number_input("Aporte Mensal (R$)", value=0.0, step=100.0)

# Botão de escolha (Anual ou Mensal)
unidade_tempo = st.sidebar.radio("Definir horizonte em:", ["Anos", "Meses"], horizontal=True)

if unidade_tempo == "Anos":
    # O tempo começa no mínimo (1 ano)
    anos = st.sidebar.slider("Duração", 1, 30, 1, format="%d Anos")
    meses = anos * 12
else:
    # O tempo começa no mínimo (1 mês)
    meses = st.sidebar.slider("Duração", 1, 12, 1, format="%d Meses")
    anos = meses / 12

st.sidebar.divider()

st.sidebar.header("📊 Cenário Macroeconômico")
# Alterado value para 0.0
inflacao_anual = st.sidebar.number_input("Inflação Projetada - IPCA (%)", value=0.0, step=0.5) / 100

st.sidebar.divider()

tipo_taxa = st.sidebar.radio("Estratégia de Alocação:", ["Renda Fixa", "Renda Variável (Monte Carlo)"])

if tipo_taxa == "Renda Fixa":
    # Alterado value para 0.0
    taxa_anual = st.sidebar.number_input("Taxa Fixa Anual (%)", value=0.0, step=0.5) / 100
else:
    st.sidebar.write("Parâmetros do MBG:")
    # Alterados values para 0.0
    mu = st.sidebar.number_input("Retorno Esperado (Drift) %", value=0.0, step=0.5) / 100
    sigma = st.sidebar.number_input("Volatilidade (Risco) %", value=0.0, step=1.0) / 100
# --- 4. PROCESSAMENTO DOS DADOS ---
if tipo_taxa == "Renda Fixa":
    saldos, investido = calcular_fluxo_renda_fixa(valor_inicial, aporte_mensal, meses, taxa_anual)
    saldo_final_bruto = saldos[-1]
    df_grafico = pd.DataFrame({"Patrimônio": saldos})
else:
    cenarios, investido = simular_monte_carlo_mbg(valor_inicial, aporte_mensal, meses, mu, sigma)
    # Extrai a mediana (Cenário Provável) para métricas principais
    saldos = np.median(cenarios, axis=1) 
    saldo_final_bruto = saldos[-1]
    
    # Prepara os dados para a "nuvem" de cenários
    df_grafico = pd.DataFrame({
        "Cenário Otimista (95%)": np.percentile(cenarios, 95, axis=1),
        "Cenário Provável (Mediana)": saldos,
        "Cenário Pessimista (5%)": np.percentile(cenarios, 5, axis=1)
    })

total_investido = investido[-1]
lucro_bruto = saldo_final_bruto - total_investido

# Descontos Fiscais e Inflação
imposto_retido = calcular_imposto_renda(lucro_bruto, anos)
saldo_final_liquido = saldo_final_bruto - imposto_retido

# Ajuste a Valor Presente (Desconto da inflação para descobrir o poder de compra real)
fator_desconto_inflacao = (1 + inflacao_anual) ** anos
poder_de_compra_real = saldo_final_liquido / fator_desconto_inflacao

# --- 5. DASHBOARD EXECUTIVO (INTERFACE) ---
st.title("📈 CalculaInvest")
st.write("Projeção de acumulação de capital com análise de risco, inflação e tributação.")

st.markdown("### 💰 Resumo Financeiro (Fim do Período)")
col1, col2, col3, col4 = st.columns(4)

# Métricas formatadas sem casas decimais para um visual mais limpo e executivo
col1.metric("Total Investido (Custo)", f"R$ {total_investido:,.0f}")
col2.metric("Saldo Bruto Estimado", f"R$ {saldo_final_bruto:,.0f}", f"+ R$ {lucro_bruto:,.0f} de lucro")
col3.metric("Imposto de Renda Pago", f"- R$ {imposto_retido:,.0f}", "Tabela Regressiva")
col4.metric(
    "Poder de Compra Real", 
    f"R$ {poder_de_compra_real:,.0f}", 
    "Ajustado pela Inflação"
)

st.divider()

# --- 6. VISUALIZAÇÃO GRÁFICA ---
st.markdown("### 📊 Evolução Patrimonial")
if tipo_taxa == "Renda Fixa":
    st.area_chart(df_grafico)
else:
    st.line_chart(df_grafico, color=["#00FF00", "#0000FF", "#FF0000"])
    st.caption("Nota: As linhas representam os limites estatísticos após 500 simulações de mercado. Existe 90% de probabilidade de o seu saldo final ficar entre as linhas Vermelha (Pessimista) e Verde (Otimista).")

# --- 7. EXTRATO DE DADOS LIMPOS ---
with st.expander("📋 Ver Extrato de Auditoria de Dados"):
    df_export = pd.DataFrame({
        "Mês": range(meses + 1),
        "Dinheiro Investido (R$)": investido,
        "Saldo Projetado (R$)": saldos
    }).set_index("Mês")
    
    st.dataframe(df_export, use_container_width=True)
    
    st.download_button(
        label="📥 Descarregar Dados Analíticos (CSV)",
        data=df_export.to_csv().encode('utf-8'),
        file_name="projecao_financeira_v2.csv",
        mime="text/csv"
    )