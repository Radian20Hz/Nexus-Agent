import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# --- KONFIGURACJA ---
DB_DIR = "workspace/chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Lekki i szybki model

class KnowledgeBase:
    def __init__(self):
        print("[INIT] Ładowanie modelu embeddingów (to może chwilę potrwać)...")
        # Pobieramy model do zamiany tekstu na liczby (lokalnie na CPU)
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        self.vector_db = None
        self.load_db()

    def load_db(self):
        """Ładuje bazę wiedzy z dysku (jeśli istnieje)."""
        if os.path.exists(DB_DIR) and os.listdir(DB_DIR):
            self.vector_db = Chroma(persist_directory=DB_DIR, embedding_function=self.embeddings)
            print("[KNOWLEDGE] Baza wiedzy załadowana z dysku.")
        else:
            print("[KNOWLEDGE] Tworzę nową, pustą bazę wiedzy.")
            self.vector_db = None

    def ingest_file(self, file_path):
        """Połyka plik (PDF/TXT) i zapisuje w bazie wektorowej."""
        print(f"[KNOWLEDGE] Przetwarzam plik: {file_path}...")
        
        try:
            # 1. Rozpoznaj typ i załaduj
            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding="utf-8")
            
            docs = loader.load()
            
            # 2. Potnij na kawałki (Chunking)
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(docs)
            
            if not splits:
                return "Błąd: Plik wydaje się pusty lub nieczytelny."

            # 3. Zapisz w bazie wektorowej
            if self.vector_db is None:
                self.vector_db = Chroma.from_documents(
                    documents=splits, 
                    embedding=self.embeddings, 
                    persist_directory=DB_DIR
                )
            else:
                self.vector_db.add_documents(splits)
                
            print(f"[KNOWLEDGE] Sukces. Dodano {len(splits)} fragmentów.")
            return f"Przeanalizowano plik. Dodano {len(splits)} fragmentów wiedzy do pamięci długotrwałej."
            
        except Exception as e:
            return f"Błąd przetwarzania pliku: {e}"

    def search(self, query):
        """Szuka odpowiedzi w bazie."""
        if self.vector_db is None:
            return "Baza wiedzy jest pusta. Wgraj najpierw jakiś plik PDF/TXT."
        
        # Szukamy 3 najbardziej podobnych fragmentów
        try:
            results = self.vector_db.similarity_search(query, k=3)
            context = "\n---\n".join([doc.page_content for doc in results])
            return context
        except Exception as e:
            return f"Błąd szukania w bazie: {e}"