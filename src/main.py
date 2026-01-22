import os
import json
import subprocess
import re
import ollama
from duckduckgo_search import DDGS
from colorama import Fore, Style, init

# Inicjalizacja kolorów
init(autoreset=True)

# --- KONFIGURACJA ---
MODEL_NAME = "phi3" # lub llama3
WORKSPACE_DIR = "workspace"
MEMORY_FILE = os.path.join(WORKSPACE_DIR, "brain_memory.json")

if not os.path.exists(WORKSPACE_DIR): os.makedirs(WORKSPACE_DIR)

class NexusAgent:
    def __init__(self, model):
        self.model = model
        self.memory = self.load_memory()
        self.system_prompt = """
        Jesteś Nexus-Dev (v1.0) - Autonomicznym Inżynierem działającym lokalnie.
        
        NARZĘDZIA:
        1. write_file(name || content) - Tworzenie kodu.
        2. read_file(name) - Analiza plików.
        3. shell(command) - Wykonywanie komend systemowych.
        4. search(query) - Internet.
        
        ZASADY:
        - Jesteś precyzyjny.
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
        # Automatyczna zgoda dla prostych komend (opcjonalne, dla wygody)
        if command.startswith("ls") or command.startswith("cat") or command.startswith("echo"):
            pass 
        else:
            consent = input(f"{Fore.YELLOW}ZEZWOLIĆ? (t/n): {Style.RESET_ALL}")
            if consent.lower() != 't': return "Odmowa użytkownika."
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60, cwd=WORKSPACE_DIR)
            if not result.stdout and not result.stderr: return "Wykonano (brak outputu)."
            return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        except Exception as e: return f"Błąd: {e}"

    def tool_write(self, args):
        try:
            if "||" in args:
                filename, content = args.split("||", 1)
            else:
                return "Błąd: Użyj separatora || albo bloku kodu."
            
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

    def execute_tool(self, action, action_input, full_response):
        if action == "shell": return self.tool_shell(action_input)
        if action == "read_file": return self.tool_read(action_input)
        if action == "search": return self.tool_search(action_input)
        
        if action == "write_file":
            # Parser kodu z bloków ```
            if "||" not in action_input:
                code_blocks = re.findall(r"```(?:python|bash)?\n(.*?)```", full_response, re.DOTALL)
                if code_blocks:
                    return self.tool_write(f"{action_input}||{code_blocks[-1]}")
            return self.tool_write(action_input)
            
        return "Nieznane narzędzie."

    def run(self):
        self.log("╔════════════════════════════════════════╗", Fore.CYAN)
        self.log(f"║ NEXUS-AGENT v2.0 (Model: {self.model}) ║", Fore.CYAN)
        self.log("╚════════════════════════════════════════╝", Fore.CYAN)
        
        if not self.memory: self.memory = [{"role": "system", "content": self.system_prompt}]

        while True:
            try:
                user_input = input(f"\n{Fore.GREEN}USER > {Style.RESET_ALL}")
                if user_input.lower() in ['exit', 'quit']: break
                
                self.memory.append({"role": "user", "content": user_input})
                
                steps = 0
                while steps < 10:
                    steps += 1
                    # Spinner / Info o myśleniu
                    print(f"{Fore.BLACK}{Style.BRIGHT}Thinking...{Style.RESET_ALL}", end="\r")
                    
                    try:
                        response = ollama.chat(model=self.model, messages=self.memory)['message']['content']
                    except Exception as e:
                        self.log(f"Błąd LLM: {e}", Fore.RED); break

                    self.log(f"\n[AI]: {response}", Fore.BLUE)
                    self.memory.append({"role": "assistant", "content": response})
                    self.save_memory()

                    if "Final Answer:" in response: break
                    
                    # Parsing
                    action_match = re.search(r"Action:\s*(.*)", response)
                    input_match = re.search(r"Action Input:\s*(.*)", response)
                    
                    if action_match:
                        action = action_match.group(1).strip()
                        # Input może być wielolinijkowy, bierzemy pierwszą linię jako argument prosty
                        # ale przekazujemy full_response do execute_tool dla write_file
                        act_input = input_match.group(1).strip().strip('"') if input_match else ""
                        
                        self.log(f"[SYSTEM] Uruchamiam: {action}", Fore.YELLOW)
                        result = self.execute_tool(action, act_input, response)
                        
                        self.log(f"[WYNIK]: {str(result)[:200]}...", Fore.MAGENTA)
                        self.memory.append({"role": "user", "content": f"Observation: {result}"})
                    else:
                        self.memory.append({"role": "user", "content": "Observation: Please continue or use Final Answer."})
                        
            except KeyboardInterrupt: break

if __name__ == "__main__":
    agent = NexusAgent(MODEL_NAME)
    agent.run()