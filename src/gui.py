import streamlit as st
import os
import re
import ollama
from main import NexusAgent, MODEL_NAME
from voice import text_to_speech # Importujemy głos

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Nexus-Agent v3.0", page_icon="👁️", layout="wide")

# --- STYLE CSS ---
st.markdown("""
<style>
    .stTextInput > div > div > input { background-color: #000000; color: #00FF00; font-family: monospace; }
    .stMarkdown { font-family: 'Segoe UI', sans-serif; }
    div.stButton > button { background-color: #222; color: white; border: 1px solid #444; }
</style>
""", unsafe_allow_html=True)

# --- INICJALIZACJA ---
if "agent" not in st.session_state:
    st.session_state.agent = NexusAgent(MODEL_NAME)

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR (PANEL STEROWANIA) ---
with st.sidebar:
    st.title("👁️ Nexus Vision")
    
    # 1. KAMERA
    st.markdown("### 📸 Oczy Agenta")
    enable_camera = st.toggle("Włącz Kamerę")
    img_file_buffer = None
    
    if enable_camera:
        img_file_buffer = st.camera_input("Pokaż coś Agentowi")
    
    # 2. GŁOS
    st.markdown("### 🔊 Moduł Głosu")
    enable_voice = st.toggle("Mów do mnie (TTS)", value=False)
    
    # 3. RAG
    st.markdown("---")
    st.markdown("### 📚 Baza Wiedzy")
    uploaded_file = st.file_uploader("Dodaj plik", type=["pdf", "txt"])
    if uploaded_file:
        save_path = os.path.join("workspace", uploaded_file.name)
        with open(save_path, "wb") as f: f.write(uploaded_file.getbuffer())
        with st.spinner("Trawię dane..."):
            st.session_state.agent.knowledge.ingest_file(save_path)
        st.success("Wgrano!")

    # 4. RESET
    st.markdown("---")
    if st.button("🔴 RESET PAMIĘCI"):
        st.session_state.messages = []
        st.session_state.agent.memory = [{"role": "system", "content": st.session_state.agent.system_prompt}]
        st.rerun()

# --- LOGIKA KAMERY (AUTO-ANALIZA) ---
if img_file_buffer is not None:
    # Zapisz zdjęcie
    bytes_data = img_file_buffer.getvalue()
    img_path = os.path.join("workspace", "camera_capture.jpg")
    with open(img_path, "wb") as f:
        f.write(bytes_data)
    
    # Jeśli użytkownik zrobił zdjęcie, automatycznie wyślij je do analizy
    # Ale tylko jeśli nie zrobiliśmy tego w tej samej sekundzie (zapobieganie pętli)
    if "last_photo" not in st.session_state or st.session_state.last_photo != len(bytes_data):
        st.session_state.last_photo = len(bytes_data)
        prompt = "Spójrz na plik camera_capture.jpg. Opisz co widzisz i jeśli to tekst lub kod - przepisz go."
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.agent.memory.append({"role": "user", "content": prompt})
        # Wymuszamy odświeżenie, żeby czat "zauważył" nową wiadomość
        st.rerun()

# --- CZAT ---
st.title("🧠 Nexus-Agent")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Jeśli to wiadomość asystenta i ma plik audio, odtwórz go
        if message["role"] == "assistant" and "audio" in message:
            st.audio(message["audio"], format="audio/mp3", start_time=0)

# --- POLE TEKSTOWE ---
if prompt := st.chat_input("Wpisz polecenie..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.agent.memory.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            with st.spinner("Przetwarzam..."):
                # GŁÓWNA PĘTLA MYŚLENIA
                response = ollama.chat(model=MODEL_NAME, messages=st.session_state.agent.memory)['message']['content']
                
                full_response += response
                message_placeholder.markdown(full_response)
                
                # TOOL USE
                action_match = re.search(r"Action:\s*(.*)", response)
                input_match = re.search(r"Action Input:\s*(.*)", response)
                
                if action_match:
                    action = action_match.group(1).strip()
                    act_input = input_match.group(1).strip().strip('"') if input_match else ""
                    st.toast(f"🛠️ {action}", icon="⚡")
                    
                    result = st.session_state.agent.execute_tool(action, act_input, response)
                    
                    obs = f"\n\n**Observation:**\n```\n{result}\n```"
                    full_response += obs
                    message_placeholder.markdown(full_response)
                    
                    st.session_state.agent.memory.append({"role": "assistant", "content": response})
                    st.session_state.agent.memory.append({"role": "user", "content": f"Observation: {result}"})
                else:
                    st.session_state.agent.memory.append({"role": "assistant", "content": response})
                
                st.session_state.agent.save_memory()
                
                # GENEROWANIE GŁOSU (Jeśli włączone)
                audio_path = None
                if enable_voice:
                    audio_path = text_to_speech(response)
                    if audio_path:
                        st.audio(audio_path, format="audio/mp3")

        except Exception as e:
            st.error(f"Błąd: {e}")
        
        # Zapisz wiadomość (i ścieżkę do audio) w historii sesji
        msg_data = {"role": "assistant", "content": full_response}
        if enable_voice and audio_path:
             msg_data["audio"] = audio_path
        st.session_state.messages.append(msg_data)