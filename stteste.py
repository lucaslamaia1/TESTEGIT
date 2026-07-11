import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="CalculaInvest", page_icon="📈", layout="wide")

# CSS personalizado para afinar detalhes visuais
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: clamp(20px, 2vw, 32px) !important; font-weight: 700; color: #1E88E5; }
    [data-testid="stMetricDelta"] > div { font-size: 16px !important; }
    .st-emotion-cache-1v0mbdj > img { border-radius: 10px; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
</style>
""", unsafe_allow_html=True)

# --- INTEGRAÇÃO COM BANCO CENTRAL DO BRASIL (API) ---
@st.cache_data(ttl=86400)
def obter_inflacao_bcb():
    """Procura a mediana da projeção do IPCA para o ano atual no Boletim Focus (BCB)"""
    try:
        ano_atual = datetime.datetime.now().year
        url = f"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?$top=1&$filter=Indicador%20eq%20'IPCA'%20and%20DataReferencia%20eq%20'{ano_atual}'&$orderby=Data%20desc&$format=json"
        
        resposta = requests.get(url, timeout=5)
        dados = resposta.json()
        
        inflacao_projetada = dados['value'][0]['Mediana']
        return float(inflacao_projetada)
    except:
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
with st.sidebar:
    st.header("🎯 Parâmetros do Investimento")
    st.write("Configure o seu planeamento abaixo:")

    with st.expander("💰 1. Valores Iniciais", expanded=True):
        valor_inicial = st.number_input("Dinheiro guardado hoje (R$)", value=0.0, step=1000.0)
        aporte_mensal = st.number_input("Aporte mensal (R$)", value=0.0, step=100.0)

    with st.expander("⏳ 2. Prazo", expanded=True):
        unidade_tempo = st.radio("Definir tempo em:", ["Anos", "Meses"], horizontal=True)
        if unidade_tempo == "Anos":
            anos = st.slider("Tempo de investimento", 1, 30, 5, format="%d Anos")
            meses = anos * 12
        else:
            meses = st.slider("Tempo de investimento", 1, 12, 6, format="%d Meses")
            anos = meses / 12

    with st.expander("📈 3. Rentabilidade", expanded=True):
        tipo_investimento = st.selectbox(
            "Tipo de Investimento", 
            ["Renda Fixa", "Renda Variável"]
        )
        
        if tipo_investimento == "Renda Fixa":
            st.info("Perfil: Seguro e Previsível")
            taxa_anual = st.number_input("Rendimento Anual Esperado (%)", value=10.0, step=0.5) / 100
        else:
            perfil = st.select_slider(
                "O seu perfil de risco:",
                options=["Conservador", "Moderado", "Arrojado"],
                value="Moderado"
            )
            if perfil == "Conservador": mu, sigma = 0.08, 0.10
            elif perfil == "Moderado": mu, sigma = 0.12, 0.20
            else: mu, sigma = 0.18, 0.35

    st.subheader("📊 Dados Macroeconómicos")
    inflacao_atual_bcb = obter_inflacao_bcb()
    
    with st.expander("⚙️ Inflação (Automática BCB)"):
        st.caption("🟢 Ligação ativa ao Banco Central")
        inflacao_anual = st.number_input(
            "Projeção do IPCA (%)", 
            value=inflacao_atual_bcb, 
            step=0.1,
            help="Atualizado automaticamente via API do Boletim Focus."
        ) / 100

# --- 4. PROCESSAMENTO ---
if tipo_investimento == "Renda Fixa":
    saldos, investido = calcular_fluxo_renda_fixa(valor_inicial, aporte_mensal, meses, taxa_anual)
    saldo_final_bruto = saldos[-1]
else:
    cenarios, investido = simular_renda_variavel(valor_inicial, aporte_mensal, meses, mu, sigma)
    saldos = np.median(cenarios, axis=1) 
    saldo_final_bruto = saldos[-1]

total_investido = investido[-1]
lucro_bruto = saldo_final_bruto - total_investido
imposto_retido = calcular_imposto_renda(lucro_bruto, anos)
saldo_final_liquido = saldo_final_bruto - imposto_retido
poder_de_compra_real = saldo_final_liquido / ((1 + inflacao_anual) ** anos)

# --- 5. DASHBOARD EXECUTIVO (MAIN PAGE) ---
st.title("📈 CalculaInvest Dashboard")
st.markdown("Bem-vindo ao seu simulador de investimentos. Veja como o seu património pode crescer ao longo do tempo.")

st.divider()

# Métricas Principais em Layout de Cartões
st.markdown("### 💰 Resultado no Fim do Período")
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Investido", f"R$ {total_investido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
    with col2:
        delta_color = "normal" if lucro_bruto >= 0 else "inverse"
        delta_text = f"Lucro Bruto: R$ {lucro_bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        st.metric("Saldo Total Estimado", f"R$ {saldo_final_bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta_text, delta_color=delta_color)
        
    with col3:
        st.metric("Imposto de Renda", f"- R$ {imposto_retido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "Descontado no resgate", delta_color="inverse")
        
    with col4:
        st.metric("Poder de Compra Real", f"R$ {poder_de_compra_real:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "Descontando inflação", delta_color="off")

st.divider()

# --- 6. VISUALIZAÇÃO GRÁFICA AVANÇADA (PLOTLY) ---
st.markdown("### 📊 Evolução do Património")

fig = go.Figure()

# Linha do Valor Investido (Bolso)
fig.add_trace(go.Scatter(
    x=list(range(int(meses) + 1)), 
    y=investido,
    mode='lines',
    name='Total Investido (Do seu bolso)',
    line=dict(color='gray', width=2, dash='dash')
))

# Linha do Rendimento
if tipo_investimento == "Renda Fixa":
    fig.add_trace(go.Scatter(
        x=list(range(int(meses) + 1)), 
        y=saldos,
        mode='lines',
        name='Património Acumulado',
        line=dict(color='#1E88E5', width=3),
        fill='tonexty', # Preenche o espaço entre o investido e o lucro
        fillcolor='rgba(30, 136, 229, 0.2)'
    ))
else:
    # Renda Variável: Mostrar 3 Cenários
    pessimista = np.percentile(cenarios, 5, axis=1)
    otimista = np.percentile(cenarios, 95, axis=1)
    
    fig.add_trace(go.Scatter(x=list(range(int(meses) + 1)), y=otimista, mode='lines', name='Cenário Otimista', line=dict(color='#43A047', width=1, dash='dot')))
    fig.add_trace(go.Scatter(x=list(range(int(meses) + 1)), y=pessimista, mode='lines', name='Cenário Pessimista', line=dict(color='#E53935', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(67, 160, 71, 0.1)'))
    fig.add_trace(go.Scatter(x=list(range(int(meses) + 1)), y=saldos, mode='lines', name='Cenário Provável', line=dict(color='#1E88E5', width=3)))

fig.update_layout(
    xaxis_title="Meses",
    yaxis_title="Valor (R$)",
    hovermode="x unified",
    margin=dict(l=0, r=0, t=30, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig, use_container_width=True)

# --- 7. TABELA DETALHADA ---
with st.expander("📋 Ver evolução mês a mês detalhada"):
    df_export = pd.DataFrame({
        "Mês": range(int(meses) + 1),
        "O que investiu": investido,
        "Rendimento Acumulado": saldos - investido,
        "Saldo Projetado": saldos
    })
    
    # Formatação nativa de colunas para moeda no Streamlit
    st.dataframe(
        df_export,
        column_config={
            "Mês": st.column_config.NumberColumn(format="%d"),
            "O que investiu": st.column_config.NumberColumn(format="R$ %.2f"),
            "Rendimento Acumulado": st.column_config.NumberColumn(format="R$ %.2f"),
            "Saldo Projetado": st.column_config.NumberColumn(format="R$ %.2f")
        },
        use_container_width=True,
        hide_index=True
    )