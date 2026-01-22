import os
import json
import subprocess
import re
import ollama
from duckduckgo_search import DDGS
from colorama import Fore, Style, init
from knowledge import KnowledgeBase # Importujemy nasz nowy moduł

init(autoreset=True)

# --- KONFIGURACJA ---
MODEL_NAME = "phi3" # Upewnij się, że masz ten model w Ollama (lub zmień na llama3)
WORKSPACE_DIR = "workspace"
MEMORY_FILE = os.path.join(WORKSPACE_DIR, "brain_memory.json")

if not os.path.exists(WORKSPACE_DIR): os.makedirs(WORKSPACE_DIR)

class NexusAgent:
    def __init__(self, model):
        self.model = model
        self.memory = self.load_memory()
        
        # Inicjalizacja RAG
        self.knowledge = KnowledgeBase()

        self.system_prompt = """
        Jesteś Nexus-Dev - Autonomicznym Inżynierem.
        
        NARZĘDZIA:
        1. write_file(name || content) - Tworzenie kodu/plików.
        2. read_file(name) - Analiza plików z dysku.
        3. shell(command) - Wykonywanie komend systemowych.
        4. search(query) - Wyszukiwanie w internecie.
        5. consult_archive(query) - Szukanie informacji w wgranych PDFach/Dokumentach.
        
        ZASADY:
        - Jeśli użytkownik pyta o dokumenty/wiedzę, której nie masz, użyj `consult_archive`.
        - Jeśli piszesz kod, używaj bloków ```python.
        - Myśl krok po kroku.
        
        FORMAT:
        Thought: [Plan]
        Action: [Narzędzie]
        Action Input: [Dane]
        """

    def log(self, text, color=Fore.WHITE):
        print(f"{color}{text}{Style.RESET_ALL}")

    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
            except: return []
        return []

    def save_memory(self):
        clean_msgs = [{"role": m['role'], "content": m['content']} for m in self.memory]
        if len(clean_msgs) > 20: clean_msgs = [clean_msgs[0]] + clean_msgs[-19:]
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(clean_msgs, f, ensure_ascii=False, indent=2)

    # --- NARZĘDZIA ---
    def tool_shell(self, command):
        command = command.replace("`", "").strip()
        self.log(f"\n[⚠️ SECURITY ALERT] Komenda: {command}", Fore.RED)
        if command.startswith(("ls", "cat", "echo", "python", "pip")): # Auto-zgoda dla bezpiecznych
            pass 
        else:
            # W trybie GUI nie mamy input(), więc zakładamy zgodę lub blokadę. 
            # Dla bezpieczeństwa można tu dać return "Wymagana zgoda administratora"
            pass 
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60, cwd=WORKSPACE_DIR)
            if not result.stdout and not result.stderr: return "Wykonano."
            return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        except Exception as e: return f"Błąd: {e}"

    def tool_write(self, args):
        try:
            if "||" in args: filename, content = args.split("||", 1)
            else: return "Błąd formatu zapisu."
            filename = filename.replace("`", "").strip()
            path = os.path.join(WORKSPACE_DIR, filename)
            with open(path, 'w', encoding='utf-8') as f: f.write(content.strip())
            return f"Zapisano {filename}."
        except Exception as e: return f"Błąd zapisu: {e}"

    def tool_read(self, filename):
        try:
            filename = filename.replace("`", "").strip()
            path = os.path.join(WORKSPACE_DIR, filename)
            if not os.path.exists(path): return "Plik nie istnieje."
            with open(path, 'r', encoding='utf-8') as f: return f.read()
        except Exception as e: return f"Błąd odczytu: {e}"

    def tool_search(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                if not results: return "Brak wyników."
                return "\n".join([f"{r['title']}: {r['body']}" for r in results])
        except Exception as e: return f"Błąd sieci: {e}"
        
    def tool_rag(self, query):
        self.log(f"[RAG] Przeszukuję bazę wiedzy: {query}", Fore.CYAN)
        return self.knowledge.search(query)

    def execute_tool(self, action, action_input, full_response):
        if action == "shell": return self.tool_shell(action_input)
        if action == "read_file": return self.tool_read(action_input)
        if action == "search": return self.tool_search(action_input)
        if action == "consult_archive": return self.tool_rag(action_input)
        
        if action == "write_file":
            if "||" not in action_input:
                code_blocks = re.findall(r"```(?:python|bash)?\n(.*?)```", full_response, re.DOTALL)
                if code_blocks: return self.tool_write(f"{action_input}||{code_blocks[-1]}")
            return self.tool_write(action_input)
            
        return "Nieznane narzędzie."
