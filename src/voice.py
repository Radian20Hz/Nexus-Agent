from gtts import gTTS
import os

def text_to_speech(text, filename="response.mp3"):
    """Zamienia tekst na mowę (Google TTS)."""
    try:
        # Usuwamy znaki specjalne, żeby lektor nie czytał gwiazdek
        clean_text = text.replace("*", "").replace("#", "").replace("`", "")
        
        # Generowanie dźwięku (język polski)
        tts = gTTS(text=clean_text, lang='pl')
        path = os.path.join("workspace", filename)
        tts.save(path)
        return path
    except Exception as e:
        print(f"Błąd TTS: {e}")
        return None