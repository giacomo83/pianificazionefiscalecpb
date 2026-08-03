import streamlit as st
import pandas as pd
import numpy as np
import re
from sklearn.linear_model import LinearRegression
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas



#---
# -----------------------------------------------------------------------------
# GESTIONE AUTENTICAZIONE UTENTI (LOGIN)
# -----------------------------------------------------------------------------
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # Puoi configurare più utenti nei secrets, qui facciamo un controllo semplice
        user = st.session_state["username"]
        pwd = st.session_state["password"]
        
        # Recupera le credenziali dai secrets di Streamlit
        if user in st.secrets["passwords"] and pwd == st.secrets["passwords"][user]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Non salviamo la password in chiaro nello stato
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Primo accesso, mostra i campi di login
        st.markdown('<div class="main-header">🔒 Accesso Riservato</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Inserisci le credenziali fornite da Giacomo Bertè per accedere al tool.</div>', unsafe_allow_html=True)
        
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        return False
        
    elif not st.session_state["password_correct"]:
        # Password errata, riprova
        st.markdown('<div class="main-header">🔒 Accesso Riservato</div>', unsafe_allow_html=True)
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("😕 Utente o password errati")
        return False
        
    else:
        # Accesso riuscito
        return True

if not check_password():
    st.stop()  #interrompe l'esecuzione del resto dell'app se non si è loggati
#---

# Tentativo di importare PyPDF per la lettura del Bilancio Infrannuale PDF
try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# -----------------------------------------------------------------------------
# CONFIGURAZIONE PAGINA STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="TOOL DI PIANIFICAZIONE FISCALE E CONVENIENZA CPB",
    page_icon="⚖️",
    layout="wide"
)

# Custom CSS per Grafica e Tabelle
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; color: #1E3A8A; font-weight: 800; text-align: center; margin-bottom: 5px; }
    .sub-header { font-size: 1.1rem; color: #4B5563; text-align: center; margin-bottom: 25px; }
    .section-banner {
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        color: white; padding: 12px 20px; border-radius: 8px; font-weight: bold; font-size: 1.2rem; margin: 20px 0 15px 0;
        display: flex; align-items: center; gap: 10px;
    }
    .custom-table {
        width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 0.95rem; border: 1px solid #CBD5E1;
    }
    .custom-table th {
        background-color: #1E3A8A; color: white; padding: 12px; text-align: center; border: 1px solid #CBD5E1;
    }
    .custom-table td {
        padding: 10px; text-align: center; border: 1px solid #E2E8F0; background-color: #FFFFFF;
    }
    .custom-table tr:nth-child(even) td { background-color: #F8FAFC; }
    .step-box {
        background-color: #F1F5F9; border-left: 5px solid #2563EB; padding: 15px; border-radius: 6px; margin: 10px 0;
    }
    .metric-card-green { background-color: #F0FDF4; border-left: 5px solid #16A34A; padding: 15px; border-radius: 6px; }
    .metric-card-red { background-color: #FEF2F2; border-left: 5px solid #DC2626; padding: 15px; border-radius: 6px; }
    .proiezione-box { background-color: #EFF6FF; border: 1px solid #BFDBFE; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📊 TOOL DI PIANIFICAZIONE FISCALE E CONVENIENZA CPB</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Realizzato da <b>Giacomo Bertè</b> | Analisi Triennale e Simulazione Avanzata</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PARSER TELEMATICO (.TXT)
# -----------------------------------------------------------------------------
def parse_txt_declaration(content_text, filename="", default_idx=0):
    lines = content_text.splitlines()
    piva_cf = "Non Rilevata"
    denominazione = "Non Rilevata"
    soggetto_type = "Ditta Individuale"
    anno_imposta = None

    for line in lines:
        if line.startswith('A'):
            header_code = line[14:19].strip().upper()
            if 'RSP' in header_code:
                soggetto_type = "Società di Persone (SdP)"
            elif 'RSC' in header_code:
                soggetto_type = "Società di Capitali (SdC)"
            elif 'RPF' in header_code:
                soggetto_type = "Ditta Individuale"
            
            match_anno = re.search(r'RS[P|C|F](\d{2})', line)
            if match_anno:
                anno_imposta = 2000 + int(match_anno.group(1)) - 1
            break

    if not anno_imposta:
        match_file_year = re.search(r'(202[1-6])', filename)
        anno_imposta = int(match_file_year.group(1)) if match_file_year else (2023 + default_idx)

    for line in lines:
        if line.startswith('B'):
            piva_cf = line[1:17].strip()

            if len(piva_cf) == 16 and not piva_cf.isdigit():
                cognome = line[106:148].strip()
                denominazione = f"{cognome}".strip()
            else:
                denominazione = line[150:193].strip()
            break
            
    if denominazione == "Non Rilevata":
        for line in lines:
            if line.startswith('P'):
                match_p = re.search(r'\d{11}\s+([A-Z0-9\s\&\.\'-]{5,60})', line)
                if match_p:
                    denominazione = match_p.group(1).strip()
                    break

    def get_val(quadro, rigo):
        prefix = f"{quadro}{int(rigo):03d}"
        pattern = rf'{prefix}(\d{{3}})\s*(-?\d+)'
        matches = re.findall(pattern, content_text)
        
        if not matches:
            return 0.0
            
        vals = {int(campo): float(val) for campo, val in matches}

        if quadro == 'RE' and rigo == 23:
            if 1 in vals and vals[1] > 0: return vals[1]
            if 2 in vals and vals[2] > 0: return -vals[2]

        if quadro in ['RF', 'RG'] and rigo in [60, 28]:
            if 2 in vals and vals[2] > 0: return vals[2]
            if 1 in vals and vals[1] > 0: return -vals[1]
            
        if quadro == 'RG' and rigo == 2:
            if 5 in vals: return vals[5]
            if 1 in vals: return vals[1]
            
        return max(vals.values()) if vals else 0.0

    return {
        'piva': piva_cf, 
        'denominazione': denominazione, 
        'soggetto_type': soggetto_type,
        'year': anno_imposta,
        'RF4': get_val('RF', 4), 'RF5': get_val('RF', 5), 'RF32': get_val('RF', 32), 'RF56': get_val('RF', 56), 'RF60': get_val('RF', 60),
        'RG2': get_val('RG', 2), 'RG12': get_val('RG', 12), 'RG24': get_val('RG', 24), 'RG28': get_val('RG', 28),
        'RE6': get_val('RE', 6), 'RE20': get_val('RE', 20), 'RE23': get_val('RE', 23)
    }

def calculate_forecast(series, method, target_year_idx=4):
    y = np.array(series, dtype=float)
    if np.all(y == 0): return 0.0
    
    steps = target_year_idx - 3
    
    if method == "Regressione Lineare":
        x = np.array([1, 2, 3]).reshape(-1, 1)
        model = LinearRegression()
        model.fit(x, y)
        return max(0.0, float(model.predict([[target_year_idx]])[0]))
        
    elif method == "CAGR (Tasso Medio Annuale)":
        if y[0] <= 0: return float(y[-1] * (1.05 ** steps))
        cagr = (y[-1] / y[0]) ** (1/2) - 1
        return max(0.0, float(y[-1] * ((1 + cagr) ** steps)))
        
    elif method == "Media Pesata Tassi di Crescita":
        r1 = (y[1] - y[0]) / y[0] if y[0] != 0 else 0
        r2 = (y[2] - y[1]) / y[1] if y[1] != 0 else 0
        w = (r1 * 0.35 + r2 * 0.65)
        return max(0.0, float(y[-1] * ((1 + w) ** steps)))
        
    elif method == "Smorzamento Esponenziale":
        alpha = 0.6
        s2 = alpha * y[1] + (1 - alpha) * y[0]
        s3 = alpha * y[2] + (1 - alpha) * s2
        if steps == 1:
            return max(0.0, float(s3))
        else:
            s4 = alpha * s3 + (1 - alpha) * y[2]
            return max(0.0, float(s4))
            
    return float(y[-1])

def get_isa_substitute_rate(isa_score):
    if isa_score >= 8.0:
        return 10.0
    elif isa_score >= 6.0:
        return 12.0
    else:
        return 15.0

def parse_zucchetti_pdf(pdf_file):
    extracted_data = {'reddito': 0.0, 'found': False}
    if not PYPDF_AVAILABLE:
        return extracted_data
        
    try:
        reader = pypdf.PdfReader(pdf_file)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        clean_text = full_text.replace('\xa0', ' ')
        
        pattern = r'REDDITO/PERDITA\s*\(?\s*A\s*\+\s*B\s*-\s*C\s*-\s*D\s*\+\s*E\s*\)?\s*([\d\.\,]+)'
        match = re.search(pattern, clean_text, re.IGNORECASE)
        
        if not match:
            pattern = r'REDDITO/PERDITA\s*([\d\.\,]+)'
            match = re.search(pattern, clean_text, re.IGNORECASE)

        if match:
            val_str = match.group(1).replace('.', '').replace(',', '.')
            extracted_data['reddito'] = float(val_str)
            extracted_data['found'] = True
            
    except Exception as e:
        st.error(f"Errore durante la lettura del PDF Zucchetti: {e}")
        
    return extracted_data

# -----------------------------------------------------------------------------
# SIDEBAR - CONFIGURAZIONE
# -----------------------------------------------------------------------------
st.sidebar.title("📌 Configurazione")
section = st.sidebar.radio(
    "Seleziona il Regime Fiscale:",
    [
        "1. Regime Ordinario Impresa (RF)",
        "2. Regime Ordinario Autonomo (RE)",
        "3. Regime Semplificato Impresa (RG)",
        "4. Regime Semplificato Autonomo (RE)"
    ],
    index=0
)

st.sidebar.markdown("---")
uploaded_files = st.sidebar.file_uploader(
    "Carica i 3 file .txt delle dichiarazioni (es. 2023, 2024, 2025)",
    type=["txt"],
    accept_multiple_files=True
)

st.markdown(f'<div class="section-banner"><span>📌</span> {section}</div>', unsafe_allow_html=True)

if not uploaded_files or len(uploaded_files) < 3:
    st.info("👈 **Per iniziare, carica i 3 file `.txt` delle dichiarazioni fiscali nella barra laterale a sinistra.**")
    st.stop()

# ESECUZIONE PARSER TXT
raw_parsed = []
for idx, f in enumerate(uploaded_files):
    content = f.read().decode('utf-8', errors='ignore')
    raw_parsed.append(parse_txt_declaration(content, filename=f.name, default_idx=idx))

for f in uploaded_files:
    f.seek(0)
    content_check = f.read().decode('utf-8', errors='ignore')
    f.seek(0)
    
    quadro_rilevato = None
    for line in content_check.splitlines():
        if line.startswith('C'):
            if "RF00" in line or "RF0" in line:
                quadro_rilevato = "RF"
                break
            elif "RG00" in line or "RG0" in line:
                quadro_rilevato = "RG"
                break
            elif "RE00" in line or "RE0" in line:
                quadro_rilevato = "RE"
                break

    if quadro_rilevato:
        if "RF" in section and quadro_rilevato != "RF":
            st.error(
                f"🚨 **INCOMPATIBILITÀ REGIME FISCALE / FILE TELEMATICO**\n\n"
                f"Hai selezionato il regime **Ordinario Impresa (RF)**, ma il file `{f.name}` "
                f"contiene il **Quadro {quadro_rilevato}**.\n\n"
                f"👉 **Soluzione:** Seleziona il regime corretto nella barra laterale oppure carica il file appropriato."
            )
            st.stop()

        elif "RG" in section and quadro_rilevato != "RG":
            st.error(
                f"🚨 **INCOMPATIBILITÀ REGIME FISCALE / FILE TELEMATICO**\n\n"
                f"Hai selezionato il regime **Semplificato Impresa (RG)**, ma il file `{f.name}` "
                f"contiene il **Quadro {quadro_rilevato}**.\n\n"
                f"👉 **Soluzione:** Seleziona il regime corretto nella barra laterale oppure carica il file appropriato."
            )
            st.stop()

        elif "RE" in section and quadro_rilevato != "RE":
            st.error(
                f"🚨 **INCOMPATIBILITÀ REGIME FISCALE / FILE TELEMATICO**\n\n"
                f"Hai selezionato un regime **Autonomo / Professionisti (RE)**, ma il file `{f.name}` "
                f"contiene il **Quadro {quadro_rilevato}**.\n\n"
                f"👉 **Soluzione:** Seleziona il regime corretto nella barra laterale oppure carica il file appropriato."
            )
            st.stop()

parsed_data = sorted(raw_parsed, key=lambda x: x['year'])
if parsed_data[0]['year'] == parsed_data[1]['year']:
    for i in range(len(parsed_data)):
        parsed_data[i]['year'] = 2023 + i

for d in parsed_data:
    if d['RE6'] > 0 or d['RE20'] > 0:
        d['RE23'] = d['RE6'] - d['RE20']
        
    if d['RG12'] > 0 or d['RG24'] > 0:
        d['RG28'] = d['RG12'] - d['RG24']

    if d['RF4'] > 0 or d['RF5'] > 0:
        d['RF60'] = d['RF4'] - d['RF5'] + d['RF32'] - d['RF56']

piva_val = parsed_data[-1]['piva']
denom_val = parsed_data[-1]['denominazione']
detected_soggetto = parsed_data[-1]['soggetto_type']
years = [str(d['year']) for d in parsed_data]
year_cpb1 = str(int(years[-1]) + 1)
year_cpb2 = str(int(years[-1]) + 2)

st.markdown(f"**Contribuente / Denominazione:** `{denom_val}` | **Codice Fiscale / P.IVA:** `{piva_val}`")
st.markdown(f"**Annualità Rilevate:** `{years[0]}` | `{years[1]}` | `{years[2]}`")

if "1." in section:
    quadro_label, target_key = "Quadro RF (Impresa Ordinaria)", 'RF60'
    fields = [('RF4 UTILE', 'RF4'), ('RF5 PERDITA', 'RF5'), ('RF32 TOT. VARIAZIONI AUMENTO', 'RF32'), ('RF56 TOT. VARIAZIONI DIMINUZIONE', 'RF56'), ("RF60 REDDITO D'IMPRESA LORDO", 'RF60')]
elif "2." in section or "4." in section:
    quadro_label, target_key = "Quadro RE (Autonomo)", 'RE23'
    fields = [('RE6 TOTALE COMPENSI', 'RE6'), ('RE20 TOTALE SPESE', 'RE20'), ("RE23 REDDITO/PERDITA ATTIVITÀ PROFESSIONALI", 'RE23')]
else:
    quadro_label, target_key = "Quadro RG (Impresa Semplificata)", 'RG28'
    fields = [('RG2 RICAVI', 'RG2'), ('RG12 TOTALE COMPONENTI POSITIVI', 'RG12'), ('RG24 TOTALE COMPONENTI NEGATIVI', 'RG24'), ("RG28 REDDITO O PERDITA D'IMPRESA", 'RG28')]

st.subheader(f"📊 Storico Triennale - {quadro_label}")

col_f1, col_f2 = st.columns([2, 3])
with col_f1:
    forecast_method = st.selectbox(
        "🔮 Metodo di Previsione Reddito Atteso:",
        [
            "Proiezione Annualizzata (Prospetto Fiscale AGO Infinity)", 
            "Regressione Lineare", 
            "CAGR (Tasso Medio Annuale)", 
            "Media Pesata Tassi di Crescita", 
            "Smorzamento Esponenziale"
        ]
    )

with col_f2:
    with st.expander("ℹ️ Come funzionano i metodi di previsione?"):
        st.markdown("""
        * **Proiezione Annualizzata (Infrannuale)**: Reperisce direttamente il valore di **REDDITO/PERDITA** dal prospetto fiscale e lo proietta sui 12 mesi ($Valore \\times 12 / Mesi$).
        * **Regressione Lineare**: Proietta il trend costante calcolato sui 3 anni storici.
        * **CAGR**: Tasso annuale di crescita composto tra il primo e l'ultimo anno (valore finale/valore iniziale)^1/n]-1.
        * **Media Pesata Tassi**: Pesa maggiormente il trend recente (65% ultimo anno, 35% anno precedente).
        * **Smorzamento Esponenziale**: Attenua i picchi isolati valorizzando la stabilità.
        """)

if 'pdf_dati_memorizzati' not in st.session_state:
    st.session_state['pdf_dati_memorizzati'] = {}

infrannuali_values = {}
if forecast_method == "Proiezione Annualizzata (Prospetto Fiscale AGO Infinity)":
    st.markdown('<div class="proiezione-box">', unsafe_allow_html=True)
    st.markdown(f"#### 📐 Proiezione da REDDITO/PERDITA del Prospetto Fiscale {year_cpb1}")
    
    col_pdf1, col_pdf2 = st.columns([2, 2])
    with col_pdf1:
        months_passed = st.slider("Mesi di bilancio già maturati/contabilizzati:", 1, 11, 6, help="Es. 6 per bilancio chiuso al 30/06")
    with col_pdf2:
        pdf_zucchetti = st.file_uploader("📂 Carica Prospetto Fiscale PDF Zucchetti:", type=["pdf"])
    
    if pdf_zucchetti:
        pdf_extracted = parse_zucchetti_pdf(pdf_zucchetti)
        if pdf_extracted['found']:
            st.success(f"✅ Estratto REDDITO/PERDITA (A+B-C-D+E) dal Prospetto Fiscale: **€ {pdf_extracted['reddito']:,.2f}**")
            st.session_state['pdf_dati_memorizzati'][target_key] = float(pdf_extracted['reddito'])
            target_input_key = f"inf_input_{target_key}"
            if target_input_key not in st.session_state or st.session_state.get('last_uploaded_pdf') != pdf_zucchetti.name:
                st.session_state[target_input_key] = float(pdf_extracted['reddito'])
                st.session_state['last_uploaded_pdf'] = pdf_zucchetti.name
                st.rerun()
        else:
            st.warning("⚠️ Impossibile rilevare automaticamente il rigo REDDITO/PERDITA. Inserisci il valore manualmente.")

    st.caption(f"Inserisci o verifica il valore parziale di **REDDITO/PERDITA** maturato nei primi **{months_passed} mesi**. Formula di proiezione al 31/12: $(Valore \\div {months_passed}) \\times 12$")
    
    cols_inf = st.columns(len(fields))
    
    for i, (label, key) in enumerate(fields):
        with cols_inf[i]:
            input_widget_key = f"inf_input_{key}"
            valore_salvato = st.session_state['pdf_dati_memorizzati'].get(key, 0.0)
            if input_widget_key not in st.session_state:
                st.session_state[input_widget_key] = valore_salvato
                
            val_parziale = st.number_input(f"{label} ({months_passed} m)", key=input_widget_key)
            st.session_state['pdf_dati_memorizzati'][key] = val_parziale
            
            val_annualizzato = (val_parziale / months_passed) * 12.0
            infrannuali_values[key] = val_annualizzato
            st.caption(f"➜ Proiettato 31/12: **€ {val_annualizzato:,.2f}**")
            
    st.markdown('</div>', unsafe_allow_html=True)

predictions_dict_y1 = {}
predictions_dict_y2 = {}

for label, key in fields:
    vals = [d[key] for d in parsed_data]
    if forecast_method == "Proiezione Annualizzata (Prospetto Fiscale AGO Infinity)":
        predictions_dict_y1[key] = infrannuali_values.get(key, 0.0)
        cagr_trend = (vals[-1] / vals[0]) ** (1/2) - 1 if vals[0] > 0 else 0.02
        predictions_dict_y2[key] = predictions_dict_y1[key] * (1 + max(0.0, cagr_trend))
    else:
        predictions_dict_y1[key] = calculate_forecast(vals, forecast_method, target_year_idx=4)
        predictions_dict_y2[key] = calculate_forecast(vals, forecast_method, target_year_idx=5)

html_table = f"""<table class="custom-table">
<thead>
    <tr>
        <th>Voce Dichiarazione</th>
        <th>Anno {years[0]} (€)</th>
        <th>Trend 1</th>
        <th>Anno {years[1]} (€)</th>
        <th>Trend 2</th>
        <th>Anno {years[2]} (€)</th>
        <th>Previsione Calcolata {year_cpb1} (€)</th>
        <th>Previsione Calcolata {year_cpb2} (€)</th>
    </tr>
</thead>
<tbody>"""

for label, key in fields:
    vals = [d[key] for d in parsed_data]
    arrow1 = "🟢 ↗️" if vals[1] > vals[0] else ("🔴 ↘️" if vals[1] < vals[0] else "➡️")
    arrow2 = "🟢 ↗️" if vals[2] > vals[1] else ("🔴 ↘️" if vals[2] < vals[1] else "➡️")
    pred_val_y1 = predictions_dict_y1[key]
    pred_val_y2 = predictions_dict_y2[key]
    html_table += f"""
    <tr>
        <td><b>{label}</b></td>
        <td>{vals[0]:,.2f}</td>
        <td>{arrow1}</td>
        <td>{vals[1]:,.2f}</td>
        <td>{arrow2}</td>
        <td>{vals[2]:,.2f}</td>
        <td><b>{pred_val_y1:,.2f}</b></td>
        <td><b>{pred_val_y2:,.2f}</b></td>
    </tr>"""

html_table += "</tbody></table>"

st.subheader("📋 Tabella Dati Storici Triennali e Previsioni Calcolate")
st.markdown(html_table.strip(), unsafe_allow_html=True)

st.write(f"##### ✏️ Modifica Manuale Valori di Previsione {year_cpb1}")
manual_preds_y1 = {}
cols_inputs_y1 = st.columns(len(fields))

for i, (label, key) in enumerate(fields):
    with cols_inputs_y1[i]:
        manual_preds_y1[key] = st.number_input(
            f"{label} ({year_cpb1})",
            value=float(round(predictions_dict_y1[key], 2))
        )

st.write(f"##### ✏️ Modifica Manuale Valori di Previsione {year_cpb2}")
manual_preds_y2 = {}
cols_inputs_y2 = st.columns(len(fields))

for i, (label, key) in enumerate(fields):
    with cols_inputs_y2[i]:
        manual_preds_y2[key] = st.number_input(
            f"{label} ({year_cpb2})",
            value=float(round(predictions_dict_y2[key], 2))
        )

target_pred_income_t1 = manual_preds_y1[target_key]
target_pred_income_t2 = manual_preds_y2[target_key]

st.markdown(f"""
<div class="metric-card-green">
    <b>💰 REDDITO EFFETTIVO ATTESO PREVISTO BASE ({year_cpb1}):</b> 
    <span style="font-size:1.4rem; font-weight:bold; color:#15803D; margin-left:10px;">€ {target_pred_income_t1:,.2f}</span>
    <span style="margin-left:30px;"><b>💰 PREVISTO BASE ({year_cpb2}):</b></span>
    <span style="font-size:1.4rem; font-weight:bold; color:#15803D; margin-left:10px;">€ {target_pred_income_t2:,.2f}</span>
</div>
""", unsafe_allow_html=True)

def calculate_irpef_scaglioni(reddito_totale):
    """
    Calcola l'IRPEF lorda, l'aliquota media e il dettaglio passaggio per passaggio sui 3 scaglioni.
    """
    if reddito_totale <= 0:
        return 0.0, 0.0, []
    
    dettaglio = []
    
    # 1° Scaglione: 0 - 28.000 € (23%)
    quota1 = min(reddito_totale, 28000.0)
    imposta1 = quota1 * 0.23
    dettaglio.append({
        'da': 0.0,
        'a': quota1,
        'aliquota': 23.0,
        'imposta': imposta1
    })
    
    imposta_totale = imposta1
    
    # 2° Scaglione: 28.000 - 50.000 € (35%)
    if reddito_totale > 28000.0:
        quota2 = min(reddito_totale - 28000.0, 22000.0)
        imposta2 = quota2 * 0.35
        imposta_totale += imposta2
        dettaglio.append({
            'da': 28000.0,
            'a': 28000.0 + quota2,
            'aliquota': 35.0,
            'imposta': imposta2
        })
        
    # 3° Scaglione: Oltre 50.000 € (43%)
    if reddito_totale > 50000.0:
        quota3 = reddito_totale - 50000.0
        imposta3 = quota3 * 0.43
        imposta_totale += imposta3
        dettaglio.append({
            'da': 50000.0,
            'a': reddito_totale,
            'aliquota': 43.0,
            'imposta': imposta3
        })
        
    aliquota_media = (imposta_totale / reddito_totale) * 100.0
    return imposta_totale, aliquota_media, dettaglio

# Variabili di stato per i dettagli soci/titolare da passare al PDF
st.session_state['dettaglio_irpef_pdf'] = []

# -----------------------------------------------------------------------------
# CONFIGURAZIONE SOGGETTO E TASSAZIONE FISCALE
# -----------------------------------------------------------------------------
st.markdown('<div class="section-banner"><span>🏛️</span> CONFIGURAZIONE SOGGETTO E TASSAZIONE FISCALE</div>', unsafe_allow_html=True)

col_tax1, col_tax2 = st.columns([2, 2])

company_options = ["Ditta Individuale", "Società di Persone (SdP)", "Società di Capitali (SdC)"]
default_soggetto_idx = company_options.index(detected_soggetto) if detected_soggetto in company_options else 0

with col_tax1:
    company_type = st.selectbox(
        "🏢 Tipologia Soggetto Fiscale:",
        company_options,
        index=default_soggetto_idx
    )
    
    isa_score = st.number_input("⭐ Punteggio ISA (per aliquota Flat Tax CPB):", min_value=0.00, max_value=10.00, value=0.00, step=0.01)
    substitute_rate = get_isa_substitute_rate(isa_score)
    st.info(f"💡 Imposta Sostitutiva CPB (Flat Tax) applicabile: **{substitute_rate}%** (in base a Punteggio ISA {isa_score:.2f})")

    with st.expander("ℹ️ **Prospetto Aliquote Imposta Sostitutiva ISA (Flat Tax CPB)**"):
        st.markdown("""
        * **10%**: per un punteggio ISA pari o superiore a **8.0**
        * **12%**: per un punteggio ISA compreso tra **6.0 e 7.99**
        * **15%**: per un punteggio ISA inferiore a **6.0**
        """)

# --- CALCOLO IRPEF DISTINTO SULLE DUE ANNUALITÀ ---
with col_tax2:
    irap_rate = st.number_input("Aliquota IRAP (%):", value=0.0, step=0.1, help="Lascia 0.0% per Ditte Ind./Professionisti esenti o se non considerata nel calcolo Flat Tax CPB")

    # --- AVVISO VISIVO (WARNING / DISCLAIMER) IN EVIDENZA ---
    st.warning(
        "⚠️ **Nota metodologica:** Il calcolo dell'IRPEF e dell'aliquota media si basa sul reddito complessivo "
        "applicando la progressione per scaglioni vigenti, maggiorata delle addizionali regionali e comunali specificate analiticamente in modo distinto per ciascuna annualità, "
        "ma al lordo delle detrazioni d'imposta (es. carichi di famiglia, oneri detraibili ex art. 15 TUIR)."
    )
    
    dettaglio_irpef_struttura = []
    
    if company_type == "Società di Capitali (SdC)":
        opt_trasparenza = st.checkbox("📋 Opzione Trasparenza Fiscale (ex art. 116 TUIR)", value=False)
        
        if opt_trasparenza:
            st.write("👥 **Calcolo IRPEF Dinamico Soci in Trasparenza (SdC) con Deduzioni Puntuali:**")
            num_soci = st.number_input("Numero Soci:", min_value=1, max_value=5, value=2, key="num_soci_sdc")
            soci_info_t1 = []
            soci_info_t2 = []
            tot_quota = 0
            
            for s in range(num_soci):
                with st.expander(f"👤 Socio {s+1}", expanded=True):
                    q = st.number_input(f"Quota (%)", value=100.0/num_soci, key=f"q_sdc_{s}")
                    
                    st.markdown(f"📍 **Calcolo aliquota media Socio {s+1}**")
                    col_add1, col_add2 = st.columns(2)
                    with col_add1:
                        st.markdown(f"**Anno {year_cpb1}**")
                        add_reg_socio_t1 = st.number_input(f"Add. Regionale {year_cpb1} (%)", min_value=0.0, max_value=3.0, value=1.23, step=0.01, key=f"add_reg_sdc_t1_{s}")
                        add_com_socio_t1 = st.number_input(f"Add. Comunale {year_cpb1} (%)", value=0.80, step=0.01, key=f"add_com_sdc_t1_{s}")
                    with col_add2:
                        st.markdown(f"**Anno {year_cpb2}**")
                        add_reg_socio_t2 = st.number_input(f"Add. Regionale {year_cpb2} (%)", min_value=0.0, max_value=3.0, value=1.23, step=0.01, key=f"add_reg_sdc_t2_{s}")
                        add_com_socio_t2 = st.number_input(f"Add. Comunale {year_cpb2} (%)", value=0.80, step=0.01, key=f"add_com_sdc_t2_{s}")
                    
                    tot_add_socio_t1 = add_reg_socio_t1 + add_com_socio_t1
                    tot_add_socio_t2 = add_reg_socio_t2 + add_com_socio_t2

                    c1, c2 = st.columns(2)
                    with c1:
                        r_altri_t1 = st.number_input(f"Altri Redditi {year_cpb1} (€)", value=0.0, step=1000.0, key=f"ra_sdc_t1_{s}")
                        ded_socio_t1 = st.number_input(f"Deduzioni Personali {year_cpb1} (€)", value=0.0, step=500.0, key=f"ded_sdc_t1_{s}")
                    with c2:
                        r_altri_t2 = st.number_input(f"Altri Redditi {year_cpb2} (€)", value=0.0, step=1000.0, key=f"ra_sdc_t2_{s}")
                        ded_socio_t2 = st.number_input(f"Deduzioni Personali {year_cpb2} (€)", value=0.0, step=500.0, key=f"ded_sdc_t2_{s}")
                    
                    # Calcolo Anno T1
                    r_impr_socio_t1 = target_pred_income_t1 * (q / 100.0)
                    r_tot_socio_t1 = max(0.0, r_altri_t1 + r_impr_socio_t1 - ded_socio_t1)
                    imp_socio_base_t1, al_socio_base_t1, dettaglio_scaglioni_socio_t1 = calculate_irpef_scaglioni(r_tot_socio_t1)
                    al_socio_t1 = al_socio_base_t1 + tot_add_socio_t1
                    imp_socio_t1 = imp_socio_base_t1 + (r_tot_socio_t1 * (tot_add_socio_t1 / 100.0))
                    
                    # Calcolo Anno T2
                    r_impr_socio_t2 = target_pred_income_t2 * (q / 100.0)
                    r_tot_socio_t2 = max(0.0, r_altri_t2 + r_impr_socio_t2 - ded_socio_t2)
                    imp_socio_base_t2, al_socio_base_t2, dettaglio_scaglioni_socio_t2 = calculate_irpef_scaglioni(r_tot_socio_t2)
                    al_socio_t2 = al_socio_base_t2 + tot_add_socio_t2
                    imp_socio_t2 = imp_socio_base_t2 + (r_tot_socio_t2 * (tot_add_socio_t2 / 100.0))

                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        st.metric(f"Aliquota Media {year_cpb1}", f"{al_socio_t1:.2f}%")
                        st.caption(f"IRPEF+Locali: € {imp_socio_t1:,.2f} / Tot: € {r_tot_socio_t1:,.2f}")
                    with col_m2:
                        st.metric(f"Aliquota Media {year_cpb2}", f"{al_socio_t2:.2f}%")
                        st.caption(f"IRPEF+Locali: € {imp_socio_t2:,.2f} / Tot: € {r_tot_socio_t2:,.2f}")

                    with st.expander(f"📝 Dettaglio Scaglioni Socio {s+1}", expanded=False):
                        st.markdown(f"**--- ANNO {year_cpb1} ---**")
                        st.markdown(f"**Reddito Complessivo Socio (al netto deduzioni):** € {r_tot_socio_t1:,.2f}")
                        for item in dettaglio_scaglioni_socio_t1:
                            st.markdown(f"• Da **€ {item['da']:,.2f}** a **€ {item['a']:,.2f}** ({item['aliquota']:.0f}%): **€ {item['imposta']:,.2f}**")
                        st.markdown(f"• *Incluse addizionali regionali ({add_reg_socio_t1:.2f}%) e comunali ({add_com_socio_t1:.2f}%)*")
                        st.markdown(f"**IRPEF DOVUTA SOCIO {s+1} ({year_cpb1}):** **€ {imp_socio_t1:,.2f}**")

                        st.markdown(f"**--- ANNO {year_cpb2} ---**")
                        st.markdown(f"**Reddito Complessivo Socio (al netto deduzioni):** € {r_tot_socio_t2:,.2f}")
                        for item in dettaglio_scaglioni_socio_t2:
                            st.markdown(f"• Da **€ {item['da']:,.2f}** a **€ {item['a']:,.2f}** ({item['aliquota']:.0f}%): **€ {item['imposta']:,.2f}**")
                        st.markdown(f"• *Incluse addizionali regionali ({add_reg_socio_t2:.2f}%) e comunali ({add_com_socio_t2:.2f}%)*")
                        st.markdown(f"**IRPEF DOVUTA SOCIO {s+1} ({year_cpb2}):** **€ {imp_socio_t2:,.2f}**")
                    
                soci_info_t1.append({'quota': q, 'aliquota': al_socio_t1})
                soci_info_t2.append({'quota': q, 'aliquota': al_socio_t2})
                tot_quota += q

                dettaglio_irpef_struttura.append({
                    'soggetto': f"Socio {s+1} (Quota {q:.1f}%)",
                    't1_reddito': r_tot_socio_t1,
                    't1_aliquota': al_socio_t1,
                    't1_imposta': imp_socio_t1,
                    't1_scaglioni': dettaglio_scaglioni_socio_t1,
                    't2_reddito': r_tot_socio_t2,
                    't2_aliquota': al_socio_t2,
                    't2_imposta': imp_socio_t2,
                    't2_scaglioni': dettaglio_scaglioni_socio_t2,
                })
            
            if abs(tot_quota - 100.0) > 0.1:
                st.warning("⚠️ La somma delle quote dei soci deve essere 100%!")
                
            avg_irpef_soci_t1 = sum([(s['quota']/100.0) * s['aliquota'] for s in soci_info_t1])
            avg_irpef_soci_t2 = sum([(s['quota']/100.0) * s['aliquota'] for s in soci_info_t2])

            total_tax_rate_y1 = avg_irpef_soci_t1 + irap_rate
            total_tax_rate_y2 = avg_irpef_soci_t2 + irap_rate
            total_tax_rate = (total_tax_rate_y1 + total_tax_rate_y2) / 2.0

            company_type_pdf = "Società di Capitali (SdC in Trasparenza Fiscale)"
            st.info(f"💡 **Aliquota Media Cumulativa {year_cpb1}:** `{total_tax_rate_y1:.2f}%` | **{year_cpb2}:** `{total_tax_rate_y2:.2f}%`")
        else:
            ires_rate = st.number_input("Aliquota IRES (%):", value=24.0, step=0.1)
            total_tax_rate_y1 = ires_rate + irap_rate
            total_tax_rate_y2 = ires_rate + irap_rate
            total_tax_rate = total_tax_rate_y1
            company_type_pdf = company_type
            st.write(f"**Aliquota Complessiva SdC (IRES + IRAP):** `{total_tax_rate:.2f}%`")
    
    elif company_type == "Società di Persone (SdP)":
        st.write("👥 **Calcolo IRPEF Dinamico Soci in Trasparenza con Deduzioni Puntuali:**")
        num_soci = st.number_input("Numero Soci:", min_value=1, max_value=5, value=2, key="num_soci_sdp")
        soci_info_t1 = []
        soci_info_t2 = []
        tot_quota = 0
        
        for s in range(num_soci):
            with st.expander(f"👤 Socio {s+1}", expanded=True):
                q = st.number_input(f"Quota (%)", value=100.0/num_soci, key=f"q_{s}")
                
                st.markdown(f"📍 **Calcolo aliquota media Socio {s+1}**")
                col_add1, col_add2 = st.columns(2)
                with col_add1:
                    st.markdown(f"**Anno {year_cpb1}**")
                    add_reg_socio_t1 = st.number_input(f"Add. Regionale {year_cpb1} (%)", min_value=0.0, max_value=3.0, value=1.23, step=0.01, key=f"add_reg_sdp_t1_{s}")
                    add_com_socio_t1 = st.number_input(f"Add. Comunale {year_cpb1} (%)", value=0.80, step=0.01, key=f"add_com_sdp_t1_{s}")
                with col_add2:
                    st.markdown(f"**Anno {year_cpb2}**")
                    add_reg_socio_t2 = st.number_input(f"Add. Regionale {year_cpb2} (%)", min_value=0.0, max_value=3.0, value=1.23, step=0.01, key=f"add_reg_sdp_t2_{s}")
                    add_com_socio_t2 = st.number_input(f"Add. Comunale {year_cpb2} (%)", value=0.80, step=0.01, key=f"add_com_sdp_t2_{s}")
                
                tot_add_socio_t1 = add_reg_socio_t1 + add_com_socio_t1
                tot_add_socio_t2 = add_reg_socio_t2 + add_com_socio_t2

                c1, c2 = st.columns(2)
                with c1:
                    r_altri_t1 = st.number_input(f"Altri Redditi {year_cpb1} (€)", value=0.0, step=1000.0, key=f"ra_t1_{s}")
                    ded_socio_t1 = st.number_input(f"Deduzioni Personali {year_cpb1} (€)", value=0.0, step=500.0, key=f"ded_t1_{s}")
                with c2:
                    r_altri_t2 = st.number_input(f"Altri Redditi {year_cpb2} (€)", value=0.0, step=1000.0, key=f"ra_t2_{s}")
                    ded_socio_t2 = st.number_input(f"Deduzioni Personali {year_cpb2} (€)", value=0.0, step=500.0, key=f"ded_t2_{s}")
                
                # Calcolo Anno T1
                r_impr_socio_t1 = target_pred_income_t1 * (q / 100.0)
                r_tot_socio_t1 = max(0.0, r_altri_t1 + r_impr_socio_t1 - ded_socio_t1)
                imp_socio_base_t1, al_socio_base_t1, dettaglio_scaglioni_socio_t1 = calculate_irpef_scaglioni(r_tot_socio_t1)
                al_socio_t1 = al_socio_base_t1 + tot_add_socio_t1
                imp_socio_t1 = imp_socio_base_t1 + (r_tot_socio_t1 * (tot_add_socio_t1 / 100.0))
                
                # Calcolo Anno T2
                r_impr_socio_t2 = target_pred_income_t2 * (q / 100.0)
                r_tot_socio_t2 = max(0.0, r_altri_t2 + r_impr_socio_t2 - ded_socio_t2)
                imp_socio_base_t2, al_socio_base_t2, dettaglio_scaglioni_socio_t2 = calculate_irpef_scaglioni(r_tot_socio_t2)
                al_socio_t2 = al_socio_base_t2 + tot_add_socio_t2
                imp_socio_t2 = imp_socio_base_t2 + (r_tot_socio_t2 * (tot_add_socio_t2 / 100.0))

                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric(f"Aliquota Media {year_cpb1}", f"{al_socio_t1:.2f}%")
                    st.caption(f"IRPEF+Locali: € {imp_socio_t1:,.2f} / Tot: € {r_tot_socio_t1:,.2f}")
                with col_m2:
                    st.metric(f"Aliquota Media {year_cpb2}", f"{al_socio_t2:.2f}%")
                    st.caption(f"IRPEF+Locali: € {imp_socio_t2:,.2f} / Tot: € {r_tot_socio_t2:,.2f}")

                with st.expander(f"📝 Dettaglio Scaglioni Socio {s+1}", expanded=False):
                    st.markdown(f"**--- ANNO {year_cpb1} ---**")
                    st.markdown(f"**Reddito Complessivo Socio (al netto deduzioni):** € {r_tot_socio_t1:,.2f}")
                    for item in dettaglio_scaglioni_socio_t1:
                        st.markdown(f"• Da **€ {item['da']:,.2f}** a **€ {item['a']:,.2f}** ({item['aliquota']:.0f}%): **€ {item['imposta']:,.2f}**")
                    st.markdown(f"• *Incluse addizionali regionali ({add_reg_socio_t1:.2f}%) e comunali ({add_com_socio_t1:.2f}%)*")
                    st.markdown(f"**IRPEF DOVUTA SOCIO {s+1} ({year_cpb1}):** **€ {imp_socio_t1:,.2f}**")

                    st.markdown(f"**--- ANNO {year_cpb2} ---**")
                    st.markdown(f"**Reddito Complessivo Socio (al netto deduzioni):** € {r_tot_socio_t2:,.2f}")
                    for item in dettaglio_scaglioni_socio_t2:
                        st.markdown(f"• Da **€ {item['da']:,.2f}** a **€ {item['a']:,.2f}** ({item['aliquota']:.0f}%): **€ {item['imposta']:,.2f}**")
                    st.markdown(f"• *Incluse addizionali regionali ({add_reg_socio_t2:.2f}%) e comunali ({add_com_socio_t2:.2f}%)*")
                    st.markdown(f"**IRPEF DOVUTA SOCIO {s+1} ({year_cpb2}):** **€ {imp_socio_t2:,.2f}**")
                
            soci_info_t1.append({'quota': q, 'aliquota': al_socio_t1})
            soci_info_t2.append({'quota': q, 'aliquota': al_socio_t2})
            tot_quota += q

            dettaglio_irpef_struttura.append({
                'soggetto': f"Socio {s+1} (Quota {q:.1f}%)",
                't1_reddito': r_tot_socio_t1,
                't1_aliquota': al_socio_t1,
                't1_imposta': imp_socio_t1,
                't1_scaglioni': dettaglio_scaglioni_socio_t1,
                't2_reddito': r_tot_socio_t2,
                't2_aliquota': al_socio_t2,
                't2_imposta': imp_socio_t2,
                't2_scaglioni': dettaglio_scaglioni_socio_t2,
            })
        
        if abs(tot_quota - 100.0) > 0.1:
            st.warning("⚠️ La somma delle quote dei soci deve essere 100%!")
            
        avg_irpef_soci_t1 = sum([(s['quota']/100.0) * s['aliquota'] for s in soci_info_t1])
        avg_irpef_soci_t2 = sum([(s['quota']/100.0) * s['aliquota'] for s in soci_info_t2])

        total_tax_rate_y1 = avg_irpef_soci_t1 + irap_rate
        total_tax_rate_y2 = avg_irpef_soci_t2 + irap_rate
        total_tax_rate = (total_tax_rate_y1 + total_tax_rate_y2) / 2.0

        company_type_pdf = company_type
        st.info(f"💡 **Aliquota Media Cumulativa {year_cpb1}:** `{total_tax_rate_y1:.2f}%` | **{year_cpb2}:** `{total_tax_rate_y2:.2f}%`")
        
    else:
        st.write("👤 **Calcolo IRPEF Dinamico Titolare:**")
        with st.expander("👤 Dettaglio Titolare", expanded=True):
            st.markdown(f"📍 **Calcolo aliquota media Titolare**")
            col_add1, col_add2 = st.columns(2)
            with col_add1:
                st.markdown(f"**Anno {year_cpb1}**")
                add_reg_tit_t1 = st.number_input(f"Add. Regionale {year_cpb1} (%)", min_value=0.0, max_value=3.0, value=1.23, step=0.01, key="add_reg_tit_t1")
                add_com_tit_t1 = st.number_input(f"Add. Comunale {year_cpb1} (%)", value=0.80, step=0.01, key="add_com_tit_t1")
            with col_add2:
                st.markdown(f"**Anno {year_cpb2}**")
                add_reg_tit_t2 = st.number_input(f"Add. Regionale {year_cpb2} (%)", min_value=0.0, max_value=3.0, value=1.23, step=0.01, key="add_reg_tit_t2")
                add_com_tit_t2 = st.number_input(f"Add. Comunale {year_cpb2} (%)", value=0.80, step=0.01, key="add_com_tit_t2")
            
            tot_add_tit_t1 = add_reg_tit_t1 + add_com_tit_t1
            tot_add_tit_t2 = add_reg_tit_t2 + add_com_tit_t2

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                altri_redditi_ditta_t1 = st.number_input(f"Altri Redditi {year_cpb1} (€):", value=0.0, step=1000.0, key="altri_r_ditta_t1")
                deduzioni_t1 = st.number_input(f"Deduzioni/Oneri Deducibili {year_cpb1} (€):", value=0.0, step=500.0, key="ded_ditta_t1")
            with col_d2:
                altri_redditi_ditta_t2 = st.number_input(f"Altri Redditi {year_cpb2} (€):", value=0.0, step=1000.0, key="altri_r_ditta_t2")
                deduzioni_t2 = st.number_input(f"Deduzioni/Oneri Deducibili {year_cpb2} (€):", value=0.0, step=500.0, key="ded_ditta_t2")
            
            # Anno T1
            reddito_totale_ditta_t1 = max(0.0, target_pred_income_t1 + altri_redditi_ditta_t1 - deduzioni_t1)
            imp_ditta_base_t1, irpef_base_ditta_t1, dettaglio_scaglioni_t1 = calculate_irpef_scaglioni(reddito_totale_ditta_t1)
            irpef_ditta_t1 = irpef_base_ditta_t1 + tot_add_tit_t1
            imp_ditta_t1 = imp_ditta_base_t1 + (reddito_totale_ditta_t1 * (tot_add_tit_t1 / 100.0))
            
            # Anno T2
            reddito_totale_ditta_t2 = max(0.0, target_pred_income_t2 + altri_redditi_ditta_t2 - deduzioni_t2)
            imp_ditta_base_t2, irpef_base_ditta_t2, dettaglio_scaglioni_t2 = calculate_irpef_scaglioni(reddito_totale_ditta_t2)
            irpef_ditta_t2 = irpef_base_ditta_t2 + tot_add_tit_t2
            imp_ditta_t2 = imp_ditta_base_t2 + (reddito_totale_ditta_t2 * (tot_add_tit_t2 / 100.0))

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric(f"Aliquota Media {year_cpb1}", f"{irpef_ditta_t1:.2f}%")
                st.caption(f"IRPEF+Locali: € {imp_ditta_t1:,.2f} / Tot: € {reddito_totale_ditta_t1:,.2f}")
            with col_m2:
                st.metric(f"Aliquota Media {year_cpb2}", f"{irpef_ditta_t2:.2f}%")
                st.caption(f"IRPEF+Locali: € {imp_ditta_t2:,.2f} / Tot: € {reddito_totale_ditta_t2:,.2f}")

            with st.expander("📝 Dettaglio del Calcolo per Scaglioni", expanded=False):
                st.markdown(f"**--- ANNO {year_cpb1} ---**")
                st.markdown(f"**Reddito Complessivo Considerato (al netto deduzioni):** € {reddito_totale_ditta_t1:,.2f}")
                for item in dettaglio_scaglioni_t1:
                    st.markdown(f"• Da **€ {item['da']:,.2f}** a **€ {item['a']:,.2f}** ({item['aliquota']:.0f}%): **€ {item['imposta']:,.2f}**")
                st.markdown(f"• *Incluse addizionali regionali ({add_reg_tit_t1:.2f}%) e comunali ({add_com_tit_t1:.2f}%)*")
                st.markdown(f"**IRPEF NETTA DOVUTA ({year_cpb1}):** **€ {imp_ditta_t1:,.2f}**")

                st.markdown(f"**--- ANNO {year_cpb2} ---**")
                st.markdown(f"**Reddito Complessivo Considerato (al netto deduzioni):** € {reddito_totale_ditta_t2:,.2f}")
                for item in dettaglio_scaglioni_t2:
                    st.markdown(f"• Da **€ {item['da']:,.2f}** a **€ {item['a']:,.2f}** ({item['aliquota']:.0f}%): **€ {item['imposta']:,.2f}**")
                st.markdown(f"• *Incluse addizionali regionali ({add_reg_tit_t2:.2f}%) e comunali ({add_com_tit_t2:.2f}%)*")
                st.markdown(f"**IRPEF NETTA DOVUTA ({year_cpb2}):** **€ {imp_ditta_t2:,.2f}**")
        
        total_tax_rate_y1 = irpef_ditta_t1 + irap_rate
        total_tax_rate_y2 = irpef_ditta_t2 + irap_rate
        total_tax_rate = (total_tax_rate_y1 + total_tax_rate_y2) / 2.0
        company_type_pdf = company_type
        st.info(f"💡 **Aliquota Complessiva {year_cpb1}:** `{total_tax_rate_y1:.2f}%` | **{year_cpb2}:** `{total_tax_rate_y2:.2f}%`")

        dettaglio_irpef_struttura.append({
            'soggetto': "Titolare Ditta Individuale",
            't1_reddito': reddito_totale_ditta_t1,
            't1_aliquota': irpef_ditta_t1,
            't1_imposta': imp_ditta_t1,
            't1_scaglioni': dettaglio_scaglioni_t1,
            't2_reddito': reddito_totale_ditta_t2,
            't2_aliquota': irpef_ditta_t2,
            't2_imposta': imp_ditta_t2,
            't2_scaglioni': dettaglio_scaglioni_t2,
        })

st.session_state['dettaglio_irpef_pdf'] = dettaglio_irpef_struttura

# -----------------------------------------------------------------------------
# INPUT CPB BIENNALE & CONVENIENZA
# -----------------------------------------------------------------------------
st.markdown('<div class="section-banner"><span>📅</span> INSERIMENTO DATI CPB SULLE 2 ANNUALITÀ (CPB)</div>', unsafe_allow_html=True)

col_cpb_y1, col_cpb_y2 = st.columns(2)

with col_cpb_y1:
    st.markdown(f"### 🗓️ Anno 1 CPB ({year_cpb1})")
    exp_income_y1 = st.number_input(f"Reddito Atteso Previsto {year_cpb1} (€):", value=float(target_pred_income_t1))
    cpb_proposal_y1 = st.number_input(f"Proposta CPB Agenzia delle Entrate {year_cpb1} (€):", value=0.00, step=100.0)

with col_cpb_y2:
    st.markdown(f"### 🗓️ Anno 2 CPB ({year_cpb2})")
    exp_income_y2 = st.number_input(f"Reddito Atteso Previsto {year_cpb2} (€):", value=float(target_pred_income_t2))
    cpb_proposal_y2 = st.number_input(f"Proposta CPB Agenzia delle Entrate {year_cpb2} (€):", value=0.00, step=100.0)

# -----------------------------------------------------------------------------
# BREAK-EVEN POINT & RISULTATO FINALE (DETTAGLIATO E SUDDIVISO PER ANNO)
# -----------------------------------------------------------------------------
st.markdown('<div class="section-banner"><span>🧮</span> ANALISI DETTAGLIATA E BREAK-EVEN POINT PASSAGGIO DOPO PASSAGGIO</div>', unsafe_allow_html=True)

with st.expander("❓ **Come viene calcolata la convenienza e cos'è il Reddito Soglia? (Clicca per leggere)**", expanded=False):
    st.markdown("""
    ### 🎈 Cos'è il Concordato Preventivo Biennale (CPB)?
    Il Concordato Preventivo Biennale è uno strumento con cui l'Agenzia delle Entrate propone al contribuente un reddito concordato valido per due anni. Se il contribuente aderisce, accetta di determinare le imposte dirette su quel reddito concordato, indipendentemente dal reddito effettivamente conseguito, salvo i casi di decadenza o cessazione previsti dalla normativa.
    
    ---
    
    ### 1️⃣ Come calcoliamo le tasse con il Concordato?
    * **Parte Base (Storica):** Paghi le tue tasse normali (es. IRPEF/IRES + IRAP + Addizionali Locali) sul reddito concordato fino al livello storico.
    * **Parte Extra (Maggiorazione):** Se la proposta dello Stato è più alta del tuo reddito passato, sull'aumento paghi una **Flat Tax super scontata** (10%, 12% o 15% in base al punteggio ISA).
    
    ---
    
    ### 2️⃣ Cos'è il "Reddito Soglia" (Break-Even Point)?
    È il reddito di pareggio. Sono i componenti positivi esatti oltre i quali il Concordato inizia a farti **risparmiare soldi**.
    *  Reddito effettivo atteso = Reddito Bep -> i due regimi si equivalgono
    *  Reddito effettivo atteso < Reddito Bep -> regime ordinario
    *  Reddito effettivo atteso > Reddito Bep -> regime CPB
    
    $$\\text{Reddito Soglia} = \\frac{\\text{Tasse Totali con il CPB}}{\\text{Tua Aliquota di Tasse Ordinaria}}$$
    """)

def calc_annual_taxes_detailed(income_atteso, prop_cpb, tax_rate_std, flat_tax_rate, base_historical):
    tax_ordinary = income_atteso * (tax_rate_std / 100.0)
    
    base_ordinaria_cpb = min(prop_cpb, base_historical)
    incremento_cpb = max(0.0, prop_cpb - base_historical)
    
    tax_cpb_base = base_ordinaria_cpb * (tax_rate_std / 100.0)
    tax_cpb_flat = incremento_cpb * (flat_tax_rate / 100.0)
    tax_cpb_total = tax_cpb_base + tax_cpb_flat
    
    savings = tax_ordinary - tax_cpb_total
    
    bep = tax_cpb_total / (tax_rate_std / 100.0) if tax_rate_std > 0 else 0
    
    return {
        'tax_ordinary': tax_ordinary,
        'base_ordinaria_cpb': base_ordinaria_cpb,
        'incremento_cpb': incremento_cpb,
        'tax_cpb_base': tax_cpb_base,
        'tax_cpb_flat': tax_cpb_flat,
        'tax_cpb_total': tax_cpb_total,
        'savings': savings,
        'bep': bep
    }

base_hist_2025 = parsed_data[-1][target_key]

res_y1 = calc_annual_taxes_detailed(exp_income_y1, cpb_proposal_y1, total_tax_rate_y1, substitute_rate, base_hist_2025)
res_y2 = calc_annual_taxes_detailed(exp_income_y2, cpb_proposal_y2, total_tax_rate_y2, substitute_rate, base_hist_2025)

tot_exp_income = exp_income_y1 + exp_income_y2
tot_cpb_proposal = cpb_proposal_y1 + cpb_proposal_y2
tot_tax_ord = res_y1['tax_ordinary'] + res_y2['tax_ordinary']
tot_tax_cpb = res_y1['tax_cpb_total'] + res_y2['tax_cpb_total']
tot_savings = res_y1['savings'] + res_y2['savings']
tot_bep = res_y1['bep'] + res_y2['bep']

st.subheader("⚖️ Valutazione Dettagliata Annuale")

if cpb_proposal_y1 == 0 and cpb_proposal_y2 == 0:
    st.warning("👈 **Inserisci i valori della Proposta CPB inviati dall'Agenzia delle Entrate per calcolare la convenienza.**")
else:
    col_det_y1, col_det_y2 = st.columns(2)
    
    with col_det_y1:
        st.markdown(f"### 📌 Dettaglio Anno {year_cpb1}")
        
        box_class_y1 = "metric-card-green" if res_y1['savings'] >= 0 else "metric-card-red"
        st.markdown(f"""
        <div class="{box_class_y1}">
            <b>1️⃣ REGIME ORDINARIO (Senza CPB)</b><br>
            • Tasse Ordinarie incl. Locali ({total_tax_rate_y1:.2f}% su € {exp_income_y1:,.2f}):<br>
            &nbsp;&nbsp;&nbsp;&nbsp;<b>€ {exp_income_y1:,.2f} × {total_tax_rate_y1:.2f}% = € {res_y1['tax_ordinary']:,.2f}</b>
            <hr style="margin:8px 0;">
            <b>2️⃣ REGIME CONCORDATO PREVENTIVO BIENNALE (Con CPB)</b><br>
            • Quota Base ({total_tax_rate_y1:.2f}% su € {res_y1['base_ordinaria_cpb']:,.2f}):<br>
            &nbsp;&nbsp;&nbsp;&nbsp;€ {res_y1['base_ordinaria_cpb']:,.2f} × {total_tax_rate_y1:.2f}% = <b>€ {res_y1['tax_cpb_base']:,.2f}</b><br>
            • Quota Incrementale Flat Tax ({substitute_rate}% su € {res_y1['incremento_cpb']:,.2f}):<br>
            &nbsp;&nbsp;&nbsp;&nbsp;€ {res_y1['incremento_cpb']:,.2f} × {substitute_rate}% = <b>€ {res_y1['tax_cpb_flat']:,.2f}</b><br>
            • <b>Totale Tasse CPB {year_cpb1}:</b> € {res_y1['tax_cpb_base']:,.2f} + € {res_y1['tax_cpb_flat']:,.2f} = <b>€ {res_y1['tax_cpb_total']:,.2f}</b>
            <hr style="margin:8px 0;">
            <b>3️⃣ CALCOLO RISPARMIO FISCALE & BREAK-EVEN POINT</b><br>
            • <b>Risparmio Fiscale {year_cpb1}:</b> € {res_y1['tax_ordinary']:,.2f} - € {res_y1['tax_cpb_total']:,.2f} = <b style="font-size:1.1rem;">€ {res_y1['savings']:,.2f}</b><br>
            • <b>Reddito Soglia (Break-Even):</b> € {res_y1['tax_cpb_total']:,.2f} ÷ {total_tax_rate_y1:.2f}% = <b>€ {res_y1['bep']:,.2f}</b>
        </div>
        """, unsafe_allow_html=True)

    with col_det_y2:
        st.markdown(f"### 📌 Dettaglio Anno {year_cpb2}")
        
        box_class_y2 = "metric-card-green" if res_y2['savings'] >= 0 else "metric-card-red"
        st.markdown(f"""
        <div class="{box_class_y2}">
            <b>1️⃣ REGIME ORDINARIO (Senza CPB)</b><br>
            • Tasse Ordinarie incl. Locali ({total_tax_rate_y2:.2f}% su € {exp_income_y2:,.2f}):<br>
            &nbsp;&nbsp;&nbsp;&nbsp;<b>€ {exp_income_y2:,.2f} × {total_tax_rate_y2:.2f}% = € {res_y2['tax_ordinary']:,.2f}</b>
            <hr style="margin:8px 0;">
            <b>2️⃣ REGIME CONCORDATO PREVENTIVO BIENNALE (Con CPB)</b><br>
            • Quota Base ({total_tax_rate_y2:.2f}% su € {res_y2['base_ordinaria_cpb']:,.2f}):<br>
            &nbsp;&nbsp;&nbsp;&nbsp;€ {res_y2['base_ordinaria_cpb']:,.2f} × {total_tax_rate_y2:.2f}% = <b>€ {res_y2['tax_cpb_base']:,.2f}</b><br>
            • Quota Incrementale Flat Tax ({substitute_rate}% su € {res_y2['incremento_cpb']:,.2f}):<br>
            &nbsp;&nbsp;&nbsp;&nbsp;€ {res_y2['incremento_cpb']:,.2f} × {substitute_rate}% = <b>€ {res_y2['tax_cpb_flat']:,.2f}</b><br>
            • <b>Totale Tasse CPB {year_cpb2}:</b> € {res_y2['tax_cpb_base']:,.2f} + € {res_y2['tax_cpb_flat']:,.2f} = <b>€ {res_y2['tax_cpb_total']:,.2f}</b>
            <hr style="margin:8px 0;">
            <b>3️⃣ CALCOLO RISPARMIO FISCALE & BREAK-EVEN POINT</b><br>
            • <b>Risparmio Fiscale {year_cpb2}:</b> € {res_y2['tax_ordinary']:,.2f} - € {res_y2['tax_cpb_total']:,.2f} = <b style="font-size:1.1rem;">€ {res_y2['savings']:,.2f}</b><br>
            • <b>Reddito Soglia (Break-Even Point):</b> € {res_y2['tax_cpb_total']:,.2f} ÷ {total_tax_rate_y2:.2f}% = <b>€ {res_y2['bep']:,.2f}</b>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 RIEPILOGO CONSOLIDATO BIENNIO")
    
    if tot_savings >= 0:
        st.markdown(f"""
        <div class="metric-card-green" style="font-size:1.1rem;">
            🏆 <b>ESITO FINALE: CPB CONVENIENTE</b><br>
            • Tasse Totali Regime Ordinario: <b>€ {tot_tax_ord:,.2f}</b><br>
            • Tasse Totali Regime CPB: <b>€ {tot_tax_cpb:,.2f}</b><br>
            • 💰 <b>RISPARMIO FISCALE NETTO COMPLESSIVO: € {tot_savings:,.2f}</b><br>
            • 📈 <b>Reddito Soglia Totale Biennio (Break-Even): € {tot_bep:,.2f}</b> (Reddito Atteso Previsto: € {tot_exp_income:,.2f})
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="metric-card-red" style="font-size:1.1rem;">
            ⚠️ <b>ESITO FINALE: CPB NON CONVENIENTE</b><br>
            • Tasse Totali Regime Ordinario: <b>€ {tot_tax_ord:,.2f}</b><br>
            • Tasse Totali Regime CPB: <b>€ {tot_tax_cpb:,.2f}</b><br>
            • 💸 <b>SVANTAGGIO FISCALE COMPLESSIVO: € {abs(tot_savings):,.2f}</b><br>
            • 📈 <b>Reddito Soglia Totale Biennio (Break-Even): € {tot_bep:,.2f}</b> (Reddito Atteso Previsto: € {tot_exp_income:,.2f})
        </div>
        """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CANVAS PERSONALIZZATO PER PIE' DI PAGINA
# -----------------------------------------------------------------------------
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(1.5*cm, 1.5*cm, A4[0] - 1.5*cm, 1.5*cm)
        
        footer_text = "Realizzato a cura di Giacomo Bertè - Il prospetto si basa su stime e hanno valore esclusivamente previsionale e informativo."
        page_str = f"Pagina {self._pageNumber} di {page_count}"
        
        self.drawString(1.5*cm, 1.0*cm, footer_text)
        self.drawRightString(A4[0] - 1.5*cm, 1.0*cm, page_str)
        self.restoreState()

# -----------------------------------------------------------------------------
# FUNZIONE GENERAZIONE PDF PROFESSIONALE
# -----------------------------------------------------------------------------
def generate_pdf_report(
    denominazione, piva, soggetto, isa_score, substitute_rate, irap_rate,
    total_tax_rate_y1, total_tax_rate_y2,
    year1, year2, exp_y1, exp_y2, prop_y1, prop_y2,
    res_y1, res_y2, tot_exp, tot_prop, tot_ord, tot_cpb, tot_sav, tot_bep,
    base_historical=0.0, dettaglio_irpef_soci=None
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2.0*cm
    )
    
    story = []
    
    PRIMARY_COLOR = colors.HexColor("#1E3A8A")
    BG_LIGHT = colors.HexColor("#F8FAFC")
    GREEN_BG = colors.HexColor("#ECFDF5")
    RED_BG = colors.HexColor("#FEF2F2")
    BORDER_GREEN = colors.HexColor("#10B981")
    BORDER_RED = colors.HexColor("#EF4444")
    TEXT_DARK = colors.HexColor("#1E293B")
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=PRIMARY_COLOR, spaceAfter=2)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor("#64748B"), spaceAfter=6)
    section_heading = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.white, backColor=PRIMARY_COLOR, borderPadding=(5, 8, 5, 8), spaceBefore=10, spaceAfter=8)
    body_style = ParagraphStyle('BodyDark', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=TEXT_DARK)
    body_bold = ParagraphStyle('BodyBold', parent=body_style, fontName='Helvetica-Bold')
    box_title_style = ParagraphStyle('BoxTitle', parent=styles['Heading3'], fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=PRIMARY_COLOR, spaceAfter=4)
    info_style_yellow = ParagraphStyle('InfoStyleYellow', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor("#334155"))

    story.append(Paragraph("<b>REPORT DI VALUTAZIONE CONCORDATO PREVENTIVO BIENNALE</b>", title_style))
    story.append(Paragraph("Analisi statistica previsionale, valutazione di convenienza economica e simulazione fiscale", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_COLOR, spaceAfter=10))
    
    story.append(Paragraph("1. INQUADRAMENTO SOGGETTO E PARAMETRI FISCALI", section_heading))
    
    config_data = [
        [Paragraph(f"<b>Contribuente / Ditta:</b> {denominazione}", body_style), Paragraph(f"<b>Codice Fiscale / P.IVA:</b> {piva}", body_style)],
        [Paragraph(f"<b>Tipologia Soggetto:</b> {soggetto}", body_style), Paragraph(f"<b>Aliquota IRAP:</b> {irap_rate:.2f}%", body_style)],
        [Paragraph(f"<b>Punteggio ISA:</b> {isa_score:.2f}", body_style), Paragraph(f"<b>Flat Tax CPB (Imposta Sostitutiva):</b> {substitute_rate:.2f}%", body_style)],
        [Paragraph(f"<b>Aliquota Ordinaria Media ({year1}):</b> {total_tax_rate_y1:.2f}%", body_style), Paragraph(f"<b>Aliquota Ordinaria Media ({year2}):</b> {total_tax_rate_y2:.2f}%", body_style)]
    ]
    t_config = Table(config_data, colWidths=[9.0*cm, 9.0*cm])
    t_config.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    story.append(t_config)
    story.append(Spacer(1, 8))

    # --- SEZIONE DETTAGLIO IRPEF PER SOCIO / TITOLARE ---
    if dettaglio_irpef_soci:
        story.append(Paragraph("1.bis DETTAGLIO IRPEF PER SCAGLIONI (SOCI / TITOLARE) - AL NETTO DI ONERI E DEDUZIONI", section_heading))
        for socio in dettaglio_irpef_soci:
            soggetto_txt = socio['soggetto']

            match_q = re.search(r'([\d\.]+)\s*%', soggetto_txt)
            if match_q:
                val_num = float(match_q.group(1))
                soggetto_txt = re.sub(r'[\d\.]+\s*%', f"{val_num:.2f}%".replace('.', ','), soggetto_txt)

            t1_r = socio['t1_reddito']
            t1_al = socio['t1_aliquota']
            t1_imp = socio['t1_imposta']
            t1_scag = socio['t1_scaglioni']
            
            t2_r = socio['t2_reddito']
            t2_al = socio['t2_aliquota']
            t2_imp = socio['t2_imposta']
            t2_scag = socio['t2_scaglioni']
            
            socio_block = []
            socio_block.append(Paragraph(f"<b>{soggetto_txt}</b>", box_title_style))
            socio_block.append(HRFlowable(width="100%", thickness=0.5, color=PRIMARY_COLOR, spaceAfter=4))
            
            # Anno 1
            txt_t1 = f"<b>--- ANNO {year1} ---</b><br/>"
            txt_t1 += f"• Reddito Complessivo (al netto deduzioni): € {t1_r:,.2f} | Aliquota incl. Locali: {t1_al:.2f}% | Imposta Totale: € {t1_imp:,.2f}<br/>"
            for sc in t1_scag:
                txt_t1 += f"&nbsp;&nbsp;- Scaglione da € {sc['da']:,.2f} a € {sc['a']:,.2f} ({sc['aliquota']:.0f}%): € {sc['imposta']:,.2f}<br/>"
            socio_block.append(Paragraph(txt_t1, body_style))
            socio_block.append(Spacer(1, 3))
            
            # Anno 2
            txt_t2 = f"<b>--- ANNO {year2} ---</b><br/>"
            txt_t2 += f"• Reddito Complessivo (al netto deduzioni): € {t2_r:,.2f} | Aliquota incl. Locali: {t2_al:.2f}% | Imposta Totale: € {t2_imp:,.2f}<br/>"
            for sc in t2_scag:
                txt_t2 += f"&nbsp;&nbsp;- Scaglione da € {sc['da']:,.2f} a € {sc['a']:,.2f} ({sc['aliquota']:.0f}%): € {sc['imposta']:,.2f}<br/>"
            socio_block.append(Paragraph(txt_t2, body_style))
            
            t_socio_box = Table([[socio_block]], colWidths=[18.0*cm])
            t_socio_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
                ('BOX', (0,0), (-1,-1), 0.5, PRIMARY_COLOR),
                ('PADDING', (0,0), (-1,-1), 6),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(t_socio_box)
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 4))

    story.append(Paragraph("2. QUADRO REDDITI PREVISTI E PROPOSTA CONCORDATO", section_heading))
    
    redditi_headers = ["Anno / Descrizione", "Reddito Storico Base", "Reddito Atteso Previsto", "Proposta CPB AdE", "Differenza (CPB vs Atteso)"]
    row_y1 = [f"Anno {year1}", f"€ {base_historical:,.2f}", f"€ {exp_y1:,.2f}", f"€ {prop_y1:,.2f}", f"€ {(prop_y1 - exp_y1):,.2f}"]
    row_y2 = [f"Anno {year2}", f"€ {base_historical:,.2f}", f"€ {exp_y2:,.2f}", f"€ {prop_y2:,.2f}", f"€ {(prop_y2 - exp_y2):,.2f}"]
    row_tot = ["TOTALE BIENNIO", f"€ {(base_historical*2):,.2f}", f"€ {tot_exp:,.2f}", f"€ {tot_prop:,.2f}", f"€ {(tot_prop - tot_exp):,.2f}"]
    
    table_redditi_data = [[Paragraph(f"<b>{h}</b>", ParagraphStyle('H', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)) for h in redditi_headers]]
    for r in [row_y1, row_y2, row_tot]:
        is_tot = (r == row_tot)
        st_row = body_bold if is_tot else body_style
        table_redditi_data.append([Paragraph(val, st_row) for val in r])

    t_redditi = Table(table_redditi_data, colWidths=[3.2*cm, 3.7*cm, 3.7*cm, 3.7*cm, 3.7*cm])
    t_redditi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
    ]))
    story.append(t_redditi)
    story.append(Spacer(1, 8))

    expander_text = f"""
    <b>GUIDA INTERPRETATIVA E METODOLOGIA STATISTICA APPLICATA:</b><br/>
            • <b>Determinazione del Reddito Effettivo Atteso (Metodologia Statistica):</b> Il reddito stimato viene calcolato analizzando la serie storica triennale mediante algoritmi statistico-matematici, quali:<br/> 
            &nbsp;&nbsp;- Regressione Lineare,<br/> 
            &nbsp;&nbsp;- Tasso di Crescita Composto CAGR,<br/> 
            &nbsp;&nbsp;- Media Pesata dei Tassi con pesi 65/35,<br/> 
            &nbsp;&nbsp;- Smorzamento Esponenziale α=0.6,<br/> 
            &nbsp;&nbsp;- Proiezione Infrannuale Riproporzionata (importando la stampa del Prospetto Fiscale di AGO Infinity Zucchetti).<br/>
            • <b>Tassazione Regime CPB:</b> La quota di reddito concordata pari al reddito storico di base viene assoggettata ad aliquota ordinaria (IRPEF/IRES + IRAP), l'eventuale eccedenza (incremento concordato) viene tassata con l'imposta sostitutiva Flat Tax agevolata (10%, 12% o 15% in base al punteggio ISA).<br/>
            • <b>Break-Even Point (Reddito Soglia):</b> Corrisponde al punto di pareggio reddituale calcolato come <i>BEP = Imposte CPB Totali / Aliquota Ordinaria</i>. Oltre questo livello di reddito effettivo, l'adesione al CPB genera un risparmio netto. Pertanto, se:<br/>
            &nbsp;&nbsp;- <b>Reddito effettivo atteso = Reddito Bep:</b> I due regimi si equivalgono<br/>
            &nbsp;&nbsp;- <b>Reddito effettivo atteso &lt; Reddito Bep:</b> Regime Ordinario conveniente<br/>
            &nbsp;&nbsp;- <b>Reddito effettivo atteso &gt; Reddito Bep:</b> Regime CPB conveniente
    """
    t_expander = Table([[Paragraph(expander_text, info_style_yellow)]], colWidths=[18*cm])
    t_expander.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#E0F2FE")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#38BDF8")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_expander)
    story.append(Spacer(1, 10))

    story.append(Paragraph("3. ANALISI MATEMATICA E VALUTAZIONE DI CONVENIENZA", section_heading))

    def make_year_box(year, exp_inc, prop_cpb, res_dict, tax_rate, bg_col, border_col):
        content = []
        content.append(Paragraph(f"<b>DETTAGLIO CALCOLI ANNO {year}</b>", box_title_style))
        content.append(HRFlowable(width="100%", thickness=0.5, color=PRIMARY_COLOR, spaceAfter=4))
        
        txt_ord = f"""<b>1. REGIME ORDINARIO (SENZA CPB)</b><br/>
        • Imposte Ordinarie incl. Locali ({tax_rate:.2f}% su € {exp_inc:,.2f}):<br/>
        &nbsp;&nbsp;<b>€ {exp_inc:,.2f} × {tax_rate:.2f}% = € {res_dict['tax_ordinary']:,.2f}</b>
        """
        content.append(Paragraph(txt_ord, body_style))
        content.append(Spacer(1, 3))
        
        txt_cpb = f"""<b>2. REGIME CONCORDATO PREVENTIVO BIENNALE</b><br/>
        • Quota Base ({tax_rate:.2f}% su € {res_dict['base_ordinaria_cpb']:,.2f}): <b>€ {res_dict['tax_cpb_base']:,.2f}</b><br/>
        • Quota Flat Tax ({substitute_rate:.2f}% su € {res_dict['incremento_cpb']:,.2f}): <b>€ {res_dict['tax_cpb_flat']:,.2f}</b><br/>
        • <b>Totale Tasse CPB {year}:</b> € {res_dict['tax_cpb_base']:,.2f} + € {res_dict['tax_cpb_flat']:,.2f} = <b>€ {res_dict['tax_cpb_total']:,.2f}</b>
        """
        content.append(Paragraph(txt_cpb, body_style))
        content.append(Spacer(1, 3))
        
        txt_res = f"""<b>3. ESITO E BREAK-EVEN POINT REDDITUALE</b><br/>
        • <b>Risparmio Fiscale:</b> € {res_dict['tax_ordinary']:,.2f} - € {res_dict['tax_cpb_total']:,.2f} = <b>€ {res_dict['savings']:,.2f}</b><br/>
        • <b>Reddito Soglia (BEP):</b> € {res_dict['tax_cpb_total']:,.2f} ÷ {tax_rate:.2f}% = <b>€ {res_dict['bep']:,.2f}</b>
        """
        content.append(Paragraph(txt_res, body_style))
        
        t_box = Table([[content]], colWidths=[8.7*cm])
        t_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_col),
            ('BOX', (0,0), (-1,-1), 1, border_col),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        return t_box

    box_y1 = make_year_box(year1, exp_y1, prop_y1, res_y1, total_tax_rate_y1, GREEN_BG if res_y1['savings'] >= 0 else RED_BG, BORDER_GREEN if res_y1['savings'] >= 0 else BORDER_RED)
    box_y2 = make_year_box(year2, exp_y2, prop_y2, res_y2, total_tax_rate_y2, GREEN_BG if res_y2['savings'] >= 0 else RED_BG, BORDER_GREEN if res_y2['savings'] >= 0 else BORDER_RED)

    t_years = Table([[box_y1, box_y2]], colWidths=[9.0*cm, 9.0*cm])
    t_years.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(KeepTogether([t_years]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("4. QUADRO RIASSUNTIVO CONSOLIDATO BIENNIO", section_heading))
    
    is_convenient = tot_sav >= 0
    bg_final = GREEN_BG if is_convenient else RED_BG
    border_final = BORDER_GREEN if is_convenient else BORDER_RED
    status_text = "ESITO BIENNIO: CPB CONVENIENTE" if is_convenient else "ESITO BIENNIO: CPB NON CONVENIENTE"

    summary_html = f"""
    <font size="11" color="{border_final.hexval()}"><b>{status_text}</b></font><br/><br/>
    • <b>Reddito Atteso Totale Biennio:</b> € {tot_exp:,.2f}<br/>
    • <b>Proposta CPB Totale Biennio:</b> € {tot_prop:,.2f}<br/>
    • <b>Tasse Totali (Regime Ordinario):</b> € {tot_ord:,.2f}<br/>
    • <b>Tasse Totali (Regime CPB):</b> € {tot_cpb:,.2f}<br/>
    <hr color="{border_final.hexval()}" size="0.5"/>
    • <font size="9.5"><b>RISPARMIO FISCALE NETTO COMPLESSIVO: € {tot_sav:,.2f}</b></font><br/>
    • <b>Reddito Soglia Totale Biennio (Break-Even):</b> € {tot_bep:,.2f}
    """
    
    t_final = Table([[Paragraph(summary_html, body_style)]], colWidths=[18*cm])
    t_final.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_final),
        ('BOX', (0,0), (-1,-1), 1.5, border_final),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(KeepTogether([t_final]))

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer

# -----------------------------------------------------------------------------
# DOWNLOAD REPORT PDF
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📄 Generazione Report in formato PDF")

pdf_data = generate_pdf_report(
    denominazione=denom_val,
    piva=piva_val,
    soggetto=company_type_pdf,
    isa_score=isa_score,
    substitute_rate=substitute_rate,
    irap_rate=irap_rate,
    total_tax_rate_y1=total_tax_rate_y1,
    total_tax_rate_y2=total_tax_rate_y2,
    year1=year_cpb1,
    year2=year_cpb2,
    exp_y1=exp_income_y1,
    exp_y2=exp_income_y2,
    prop_y1=cpb_proposal_y1,
    prop_y2=cpb_proposal_y2,
    res_y1=res_y1,
    res_y2=res_y2,
    tot_exp=tot_exp_income,
    tot_prop=tot_cpb_proposal,
    tot_ord=tot_tax_ord,
    tot_cpb=tot_tax_cpb,
    tot_sav=tot_savings,
    tot_bep=tot_bep,
    base_historical=base_hist_2025,
    dettaglio_irpef_soci=st.session_state.get('dettaglio_irpef_pdf', [])
)

st.download_button(
    label="📥 Scarica Report in formato PDF",
    data=pdf_data,
    file_name=f"Report_CPB_{denom_val.replace(' ', '_')}.pdf",
    mime="application/pdf",
    use_container_width=True
)