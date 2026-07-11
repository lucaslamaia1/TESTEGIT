import streamlit as st
import pandas as pd
import numpy as np

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="CalculaInvest", page_icon="📈", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: clamp(14px, 1.8vw, 30px) !important; }
[data-testid="stMetricValue"] > div { text-overflow: unset !important; white-space: normal !important; word-wrap: break-word !important; overflow: visible !important; }
[data-testid="stMetricDelta"] > div { white-space: normal !important; text-overflow: unset !important; overflow: visible !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. MOTORES DE CÁLCULO (OCULTOS DO USUÁRIO) ---
def calcular_imposto_renda(lucro_bruto, anos):
    if lucro_bruto <= 0: return 0.0
    if anos <= 0.5: return lucro_bruto * 0.225
    elif anos <= 1.0: return lucro_bruto * 0.20
    elif anos <= 2.0: return lucro_bruto * 0.175
    else: return lucro_bruto * 0.15

def calcular_fluxo_renda_fixa(v_inicial, aporte, meses, taxa_anual):
    historico, investido = [v_inicial], [v_inicial]
    taxa_mensal = (1 + taxa_anual) ** (1/12) - 1
    saldo, bolso = v_inicial, v_inicial
    
    for _ in range(int(meses)):
        saldo += aporte
        bolso += aporte
        saldo += saldo * taxa_mensal
        historico.append(saldo)
        investido.append(bolso)
    return np.array(historico), np.array(investido)

@st.cache_data
def simular_renda_variavel(v_inicial, aporte, meses, mu, sigma, num_simulacoes=500):
    dt = 1 / 12
    meses_int = int(meses)
    cenarios = np.zeros((meses_int + 1, num_simulacoes))
    cenarios[0] = v_inicial
    investido = [v_inicial]
    bolso = v_inicial
    
    for t in range(1, meses_int + 1):
        bolso += aporte
        investido.append(bolso)
        Z = np.random.standard_normal(num_simulacoes)
        fator_crescimento = np.exp((mu - (sigma**2) / 2) * dt + sigma * np.sqrt(dt) * Z)
        cenarios[t] = (cenarios[t-1] + aporte) * fator_crescimento
        
    return cenarios, np.array(investido)

# --- 3. INTERFACE SIMPLIFICADA (BARRA LATERAL) ---
st.sidebar.header("🎯 Planeje seu Futuro")

valor_inicial = st.sidebar.number_input("Dinheiro guardado hoje (R$)", value=0.0, step=1000.0, help="Qual o valor que você já tem disponível para começar?")
aporte_mensal = st.sidebar.number_input("Quanto vai investir por mês? (R$)", value=0.0, step=100.0, help="Valor que você consegue poupar todo mês.")

st.sidebar.divider()

unidade_tempo = st.sidebar.radio("Como prefere definir o tempo?", ["Anos", "Meses"], horizontal=True)
if unidade_tempo == "Anos":
    anos = st.sidebar.slider("Por quanto tempo vai investir?", 1, 30, 5, format="%d Anos")
    meses = anos * 12
else:
    meses = st.sidebar.slider("Por quanto tempo vai investir?", 1, 12, 6, format="%d Meses")
    anos = meses / 12

st.sidebar.divider()

tipo_investimento = st.sidebar.selectbox(
    "Onde você vai investir esse dinheiro?", 
    ["Renda Fixa (Seguro e Previsível)", "Renda Variável (Ações/Fundos - Tem Risco)"]
)

# Configurações dinâmicas e simplificadas baseadas na escolha
if tipo_investimento == "Renda Fixa (Seguro e Previsível)":
    taxa_anual = st.sidebar.number_input("Rendimento Anual Esperado (%)", value=10.0, step=0.5, help="Exemplo: Tesouro Direto ou CDB costumam render perto da taxa Selic.") / 100
else:
    perfil = st.sidebar.select_slider(
        "Seu perfil de risco:",
        options=["Conservador", "Moderado", "Arrojado"],
        value="Moderado",
        help="O perfil define o quanto o seu patrimônio pode oscilar (subir ou cair) em busca de rendimentos maiores."
    )
    
    # Tradução do perfil para a matemática (oculto do usuário)
    if perfil == "Conservador":
        mu, sigma = 0.08, 0.10  # 8% de retorno, 10% de oscilação
    elif perfil == "Moderado":
        mu, sigma = 0.12, 0.20  # 12% de retorno, 20% de oscilação
    else:
        mu, sigma = 0.18, 0.35  # 18% de retorno, 35% de oscilação

# Painel Avançado (Escondido por padrão para não assustar o usuário comum)
with st.sidebar.expander("⚙️ Configurações Avançadas (Opcional)"):
    inflacao_anual = st.number_input("Descontar Inflação (IPCA) Anual %", value=4.5, step=0.5) / 100

# --- 4. PROCESSAMENTO ---
if tipo_investimento == "Renda Fixa (Seguro e Previsível)":
    saldos, investido = calcular_fluxo_renda_fixa(valor_inicial, aporte_mensal, meses, taxa_anual)
    saldo_final_bruto = saldos[-1]
    df_grafico = pd.DataFrame({"Patrimônio Acumulado": saldos})
else:
    cenarios, investido = simular_renda_variavel(valor_inicial, aporte_mensal, meses, mu, sigma)
    saldos = np.median(cenarios, axis=1) 
    saldo_final_bruto = saldos[-1]
    
    df_grafico = pd.DataFrame({
        "Cenário Otimista": np.percentile(cenarios, 95, axis=1),
        "Cenário Provável": saldos,
        "Cenário Pessimista": np.percentile(cenarios, 5, axis=1)
    })

total_investido = investido[-1]
lucro_bruto = saldo_final_bruto - total_investido
imposto_retido = calcular_imposto_renda(lucro_bruto, anos)
saldo_final_liquido = saldo_final_bruto - imposto_retido
poder_de_compra_real = saldo_final_liquido / ((1 + inflacao_anual) ** anos)

# --- 5. DASHBOARD EXECUTIVO ---
st.title("📈 CalculaInvest")
st.write("Veja como seu dinheiro pode crescer ao longo do tempo de forma simples.")

st.markdown("### 💰 Resultado no Fim do Período")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Dinheiro que saiu do seu bolso", f"R$ {total_investido:,.0f}")

if lucro_bruto >= 0:
    delta_text = f"+ R$ {lucro_bruto:,.0f} de rendimento"
else:
    delta_text = f"- R$ {abs(lucro_bruto):,.0f} de desvalorização"

col2.metric("Valor Total Estimado", f"R$ {saldo_final_bruto:,.0f}", delta_text)
col3.metric("Imposto de Renda (Estimativa)", f"- R$ {imposto_retido:,.0f}", "Descontado no resgate")
col4.metric("Poder de Compra Real", f"R$ {poder_de_compra_real:,.0f}", "Já descontando a inflação")

st.divider()

# --- 6. VISUALIZAÇÃO GRÁFICA ---
st.markdown("### 📊 Gráfico de Crescimento")
if tipo_investimento == "Renda Fixa (Seguro e Previsível)":
    st.area_chart(df_grafico)
else:
    st.line_chart(df_grafico, color=["#28a745", "#007bff", "#dc3545"])
    st.caption("🔍 **Como ler este gráfico:** A linha azul é o cenário mais provável. A verde é se a economia for muito bem (cenário otimista), e a vermelha se for mal (cenário pessimista).")

# --- 7. TABELA DETALHADA ---
with st.expander("📋 Ver evolução mês a mês (Tabela)"):
    df_export = pd.DataFrame({
        "Mês": range(int(meses) + 1),
        "O que você investiu (R$)": investido,
        "Saldo Projetado (R$)": saldos
    }).set_index("Mês")
    
    st.dataframe(df_export, use_container_width=True)