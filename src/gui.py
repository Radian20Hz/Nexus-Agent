import streamlit as st
import os
from main import NexusAgent, MODEL_NAME

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="Nexus-Agent AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLE CSS (Hakerski Wygląd) ---
st.markdown("""
<style>
    .stTextInput > div > div > input {
        background-color: #1E1E1E;
        color: #00FF00;
    }
    .stMarkdown {
        font-family: 'Courier New', monospace;
    }
</style>
""", unsafe_allow_html=True)

# --- INICJALIZACJA AGENTA (TYLKO RAZ) ---
if "agent" not in st.session_state:
    st.session_state.agent = NexusAgent(MODEL_NAME)
    # Przechwytujemy logi agenta, żeby nie szły do terminala, tylko do UI (opcjonalne)

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- PASEK BOCZNY ---
with st.sidebar:
    st.title("🎛️ Nexus Control")
    st.markdown("---")
    st.write(f"**Model:** `{MODEL_NAME}`")
    st.write(f"**Engine:** Ollama (Local)")
    st.markdown("---")
    if st.button("🧹 Wyczyść Pamięć"):
        st.session_state.messages = []
        st.session_state.agent.memory = [{"role": "system", "content": st.session_state.agent.system_prompt}]
        st.rerun()
    
    st.markdown("### 📂 Workspace")
    if os.path.exists("workspace"):
        files = os.listdir("workspace")
        for f in files:
            st.code(f, language="text")

# --- GŁÓWNY CZAT ---
st.title("🧠 Nexus-Dev Agent")
st.caption("Autonomiczny Inżynier Oprogramowania (v2.0)")

# Wyświetlanie historii
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- OBSŁUGA WEJŚCIA ---
if prompt := st.chat_input("Wydaj polecenie (np. 'Napisz grę w węża')..."):
    # 1. Pokaż wiadomość użytkownika
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.agent.memory.append({"role": "user", "content": prompt})

    # 2. Myślenie Agenta
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Hack: Używamy logiki agenta, ale wyświetlamy ją w UI
        # Musimy lekko zmodyfikować pętlę, żeby pasowała do Streamlit
        import ollama
        import re
        
        try:
            with st.spinner("Analizuję..."):
                # Wywołanie LLM
                response = ollama.chat(model=MODEL_NAME, messages=st.session_state.agent.memory)['message']['content']
                
                # Wyświetlamy surową odpowiedź (Thought)
                full_response += response
                message_placeholder.markdown(full_response + "▌")
                
                # Sprawdzamy czy są akcje (Tool Use)
                action_match = re.search(r"Action:\s*(.*)", response)
                input_match = re.search(r"Action Input:\s*(.*)", response)
                
                if action_match:
                    action = action_match.group(1).strip()
                    act_input = input_match.group(1).strip().strip('"') if input_match else ""
                    
                    # Pokaż, że używa narzędzia
                    st.toast(f"🛠️ Używam: {action}", icon="⚙️")
                    
                    # Wykonaj narzędzie
                    result = st.session_state.agent.execute_tool(action, act_input, response)
                    
                    # Dodaj wynik do odpowiedzi
                    observation = f"\n\n**Observation:**\n```\n{result}\n```"
                    full_response += observation
                    message_placeholder.markdown(full_response)
                    
                    # Zapisz w pamięci agenta
                    st.session_state.agent.memory.append({"role": "assistant", "content": response})
                    st.session_state.agent.memory.append({"role": "user", "content": f"Observation: {result}"})
                else:
                    # Zwykła odpowiedź
                    st.session_state.agent.memory.append({"role": "assistant", "content": response})
                
                st.session_state.agent.save_memory()
                
        except Exception as e:
            full_response = f"⚠️ Błąd: {e}"
            message_placeholder.error(full_response)
            
        # Zapisz w historii czatu UI
        st.session_state.messages.append({"role": "assistant", "content": full_response})