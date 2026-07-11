import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="CalculaInvest", page_icon="📈", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: clamp(14px, 1.8vw, 30px) !important; }
[data-testid="stMetricValue"] > div { text-overflow: unset !important; white-space: normal !important; word-wrap: break-word !important; overflow: visible !important; }
[data-testid="stMetricDelta"] > div { white-space: normal !important; text-overflow: unset !important; overflow: visible !important; }
</style>
""", unsafe_allow_html=True)

# --- INTEGRAÇÃO COM BANCO CENTRAL DO BRASIL (API) ---
@st.cache_data(ttl=86400) # Guarda em cache durante 24h para não sobrecarregar a API
def obter_inflacao_bcb():
    """Procura a mediana da projeção do IPCA para o ano atual no Boletim Focus (BCB)"""
    try:
        ano_atual = datetime.datetime.now().year
        # Chamada à API Aberta (Olinda) do Banco Central
        url = f"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?$top=1&$filter=Indicador%20eq%20'IPCA'%20and%20DataReferencia%20eq%20'{ano_atual}'&$orderby=Data%20desc&$format=json"
        
        resposta = requests.get(url, timeout=5)
        dados = resposta.json()
        
        # Extrai o valor exato da projeção mais recente
        inflacao_projetada = dados['value'][0]['Mediana']
        return float(inflacao_projetada)
    except:
        # Fallback de segurança (plano de emergência caso falhe a internet)
        # Atualizado para a projeção mais recente: 5.30% (Julho de 2026)
        return 5.30

# --- 2. MOTORES DE CÁLCULO ---
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
st.sidebar.header("🎯 Planeie o seu Futuro")

valor_inicial = st.sidebar.number_input("Dinheiro guardado hoje (R$)", value=0.0, step=1000.0)
aporte_mensal = st.sidebar.number_input("Quanto vai investir por mês? (R$)", value=0.0, step=100.0)

st.sidebar.divider()

unidade_tempo = st.sidebar.radio("Como prefere definir o tempo?", ["Anos", "Meses"], horizontal=True)

if unidade_tempo == "Anos":
    # Adicionada a key="slider_anos"
    anos = st.sidebar.slider("Por quanto tempo vai investir?", 1, 30, 5, format="%d Anos", key="slider_anos")
    meses = anos * 12
else:
    # Adicionada a key="slider_meses"
    meses = st.sidebar.slider("Por quanto tempo vai investir?", 1, 12, 6, format="%d Meses", key="slider_meses")
    anos = meses / 12

st.sidebar.divider()

tipo_investimento = st.sidebar.selectbox(
    "Onde vai investir este dinheiro?", 
    ["Renda Fixa (Seguro e Previsível)", "Renda Variável (Ações/Fundos - Com Risco)"]
)

if tipo_investimento == "Renda Fixa (Seguro e Previsível)":
    taxa_anual = st.sidebar.number_input("Rendimento Anual Esperado (%)", value=10.0, step=0.5) / 100
else:
    perfil = st.sidebar.select_slider(
        "O seu perfil de risco:",
        options=["Conservador", "Moderado", "Arrojado"],
        value="Moderado"
    )
    if perfil == "Conservador":
        mu, sigma = 0.08, 0.10
    elif perfil == "Moderado":
        mu, sigma = 0.12, 0.20
    else:
        mu, sigma = 0.18, 0.35

st.sidebar.divider()

# --- INTEGRAÇÃO DA INFLAÇÃO NA INTERFACE ---
st.sidebar.subheader("📊 Dados Macroeconómicos")
inflacao_atual_bcb = obter_inflacao_bcb()

with st.sidebar.expander("⚙️ Inflação (Automática pelo BCB)"):
    st.caption("🟢 Ligação ativa ao Banco Central")
    inflacao_anual = st.number_input(
        "Projeção do IPCA (%)", 
        value=inflacao_atual_bcb, 
        step=0.1,
        help="Este valor é atualizado automaticamente via API do Boletim Focus."
    ) / 100

# --- 4. PROCESSAMENTO ---
if tipo_investimento == "Renda Fixa (Seguro e Previsível)":
    saldos, investido = calcular_fluxo_renda_fixa(valor_inicial, aporte_mensal, meses, taxa_anual)
    saldo_final_bruto = saldos[-1]
    df_grafico = pd.DataFrame({"Património Acumulado": saldos})
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
st.write("Veja como o seu dinheiro pode crescer ao longo do tempo de forma simples.")

st.markdown("### 💰 Resultado no Fim do Período")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Dinheiro que investiu", f"R$ {total_investido:,.0f}")

if lucro_bruto >= 0:
    delta_text = f"+ R$ {lucro_bruto:,.0f} de rendimento"
else:
    delta_text = f"- R$ {abs(lucro_bruto):,.0f} de desvalorização"

col2.metric("Valor Total Estimado", f"R$ {saldo_final_bruto:,.0f}", delta_text)
col3.metric("Imposto de Renda (Estimativa)", f"- R$ {imposto_retido:,.0f}", "Descontado no resgate")
col4.metric("Poder de Compra Real", f"R$ {poder_de_compra_real:,.0f}", "Já a descontar a inflação")

st.divider()

# --- 6. VISUALIZAÇÃO GRÁFICA ---
st.markdown("### 📊 Gráfico de Crescimento")
if tipo_investimento == "Renda Fixa (Seguro e Previsível)":
    st.area_chart(df_grafico)
else:
    st.line_chart(df_grafico, color=["#28a745", "#007bff", "#dc3545"])
    st.caption("🔍 **Como ler este gráfico:** A linha azul é o cenário mais provável. A verde representa um cenário económico otimista, e a vermelha um cenário pessimista.")

# --- 7. TABELA DETALHADA ---
with st.expander("📋 Ver evolução mês a mês (Tabela)"):
    df_export = pd.DataFrame({
        "Mês": range(int(meses) + 1),
        "O que investiu (R$)": investido,
        "Saldo Projetado (R$)": saldos
    }).set_index("Mês")
    
    st.dataframe(df_export, use_container_width=True)