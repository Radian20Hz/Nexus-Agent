import os
import json
import subprocess
import re
import ollama # Nowy mózg (Lokalny)
from duckduckgo_search import DDGS
import yfinance as yf

# --- KONFIGURACJA ---
# BRAK KLUCZY API! Jesteś wolnym człowiekiem.
MODEL_NAME = "phi3" # lub "phi3", zależy co pobrałeś
WORKSPACE_DIR = "workspace"
MEMORY_FILE = "workspace/brain_memory.json"

if not os.path.exists(WORKSPACE_DIR): os.makedirs(WORKSPACE_DIR)

# --- PAMIĘĆ ---
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []
    return []

def save_memory(messages):
    # Ollama lubi prosty format, czyścimy ewentualne śmieci
    clean_msgs = []
    for msg in messages:
        clean_msgs.append({"role": msg['role'], "content": msg['content']})
            
    if len(clean_msgs) > 20: truncated = [clean_msgs[0]] + clean_msgs[-19:]
    else: truncated = clean_msgs
    
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(truncated, f, ensure_ascii=False, indent=2)

# --- NARZĘDZIA (Bez zmian - działają lokalnie) ---
def execute_shell(command):
    command = command.replace("`", "").strip()
    print(f"\n[⚠️ ALERT] Komenda: \033[91m{command}\033[0m")
    consent = input("ZEZWOLIĆ? (t/n): ")
    if consent.lower() != 't': return "Odmowa."
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, cwd=WORKSPACE_DIR)
        if not result.stdout and not result.stderr: return "Wykonano."
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Błąd: {e}"

def write_file(filename, content):
    filename = filename.replace("`", "").strip()
    try:
        with open(os.path.join(WORKSPACE_DIR, filename), 'w', encoding='utf-8') as f: f.write(content)
        return f"Zapisano {filename}."
    except Exception as e: return f"Błąd: {e}"

def read_file(filename):
    filename = filename.replace("`", "").strip()
    try:
        with open(os.path.join(WORKSPACE_DIR, filename), 'r', encoding='utf-8') as f: return f.read()
    except Exception as e: return f"Błąd: {e}"

def search_internet(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=2))
            if not results: return "Brak wyników (sprawdź internet)."
            return "\n".join([f"{r['title']}: {r['body']}" for r in results])
    except Exception as e: return f"Błąd: {e}"

tools = {
    "shell": execute_shell, "write_file": write_file, "read_file": read_file, 
    "search": search_internet
}

# --- PARSER ---
def parse_and_execute(response_text):
    if "Action:" not in response_text: return None, "Brak akcji."
    try:
        lines = response_text.split('\n')
        action = None; action_input = None
        for line in lines:
            if line.startswith("Action:"): action = line.split("Action:")[1].strip()
            elif line.startswith("Action Input:"): action_input = line.split("Action Input:")[1].strip().strip('"')
            if action and action_input: break
        
        if not action or action not in tools: return None, f"Nieznana akcja: {action}"

        if action == "write_file" and "||" not in action_input:
            code_blocks = re.findall(r"```(?:python)?\n(.*?)```", response_text, re.DOTALL)
            if code_blocks: return tools[action](action_input, code_blocks[-1].strip()), action
            else: return "Błąd zapisu: brak kodu w bloku ```", action

        if action == "write_file" and "||" in action_input:
            fn, ct = action_input.split("||", 1)
            return tools[action](fn.strip(), ct.strip()), action
            
        return tools[action](action_input), action
    except Exception as e: return f"Błąd parsowania: {e}", None

# --- PROMPT ---
system_prompt = """
Jesteś Agentem AGI (Local Llama 3).
Działasz lokalnie na komputerze użytkownika. Masz pełną kontrolę.

NARZĘDZIA:
1. write_file / read_file - Pliki.
2. shell(command) - Terminal.
3. search(query) - Internet.

FORMAT:
Thought: ...
Action: ...
Action Input: ...
"""

# --- MAIN ---
def chat_loop():
    print(f"--- AGI SYSTEM (Local {MODEL_NAME}): ONLINE ---")
    print("Brak limitów. Pełna prywatność.")
    
    messages = load_memory()
    if not messages: messages = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = input("\nTY: ")
            if user_input.lower() in ['exit', 'quit']: break
            messages.append({"role": "user", "content": user_input})
            
            steps = 0
            while steps < 10:
                steps += 1
                try:
                    # WYWOŁANIE LOKALNE
                    response_obj = ollama.chat(model=MODEL_NAME, messages=messages)
                    response = response_obj['message']['content']
                    
                except Exception as e:
                    print(f"Ollama Error: {e}")
                    print("Czy na pewno uruchomiłeś 'ollama run llama3' w tle?")
                    break
                
                print(f"\n[AI]: {response}")
                messages.append({"role": "assistant", "content": response})
                
                if "Final Answer:" in response: break
                
                if "Action:" in response:
                    result, act_name = parse_and_execute(response)
                    print(f"\033[92m[SYSTEM]:\033[0m {str(result)[:500]}...")
                    messages.append({"role": "user", "content": f"Observation: {result}"})
                else:
                    messages.append({"role": "user", "content": "Observation: Czekaj."})
                
                save_memory(messages)
                    
        except KeyboardInterrupt: break

if __name__ == "__main__":
    chat_loop()