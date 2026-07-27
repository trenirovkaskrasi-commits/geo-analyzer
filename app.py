import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# ---------------- ФУНКЦИИ ----------------
def analyze_page(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Премахване на нежелани елементи
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.extract()
            
        text = soup.get_text(separator='\n')
        words = [word for word in text.split() if word]
        word_count = len(words)
        
        h1_tags = soup.find_all('h1')
        h2_tags = soup.find_all('h2')
        h3_tags = soup.find_all('h3')
        lists = soup.find_all(['ul', 'ol'])
        tables = soup.find_all('table')
        
        return {
            'success': True,
            'word_count': word_count,
            'raw_text': " ".join(words), 
            'h1_count': len(h1_tags),
            'h2_count': len(h2_tags),
            'h3_count': len(h3_tags),
            'h1_texts': [h.get_text(strip=True) for h in h1_tags],
            'has_lists': len(lists) > 0,
            'has_tables': len(tables) > 0,
            'list_count': len(lists),
            'table_count': len(tables)
        }
        
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f"Грешка при достъп до страницата: {e}"}
    except Exception as e:
        return {'success': False, 'error': f"Неочаквана грешка: {e}"}

def optimize_content_with_gemini(text, api_key):
    try:
        genai.configure(api_key=api_key)
        
        # Взимаме всички модели, но ФИЛТРИРАМЕ тези за картинки (image/vision/embedding)
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
            and 'image' not in m.name.lower()
            and 'vision' not in m.name.lower()
            and 'embedding' not in m.name.lower()
        ]
        
        # Сортираме, за да вземем най-новите първо
        available_models.sort(reverse=True)
        
        system_instructions = """Ти си експерт по GEO (Generative Engine Optimization). 
Пренапиши предоставения текст, така че да бъде перфектно оптимизиран за AI търсачки.
Правила:
1. BLUF: Най-важният извод/факт да е първото изречение.
2. Структура: Ясни Markdown заглавия (H2, H3).
3. Форматиране: Списъци (bullet points) за характеристики/предимства.
4. Тон: Професионален, обективен.
5. FAQ: В края добави 2-3 въпроса (Често задавани въпроси).
"""
        safe_text = text[:30000] 
        full_prompt = system_instructions + "\n\nЕто текста за пренаписване:\n" + safe_text

        last_error = ""
        
        # Пробваме филтрираните модели един по един
        for model_name in available_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(full_prompt)
                return {"success": True, "optimized_text": response.text}
            except Exception as e:
                last_error = str(e)
                # Прескачаме модели, които са спрени (404) или нямат безплатен лимит (429 limit: 0)
                if "404" in last_error or "no longer available" in last_error or ("429" in last_error and "limit: 0" in last_error):
                    continue
                else:
                    return {"success": False, "error": last_error}
                    
        return {"success": False, "error": f"Не успяхме да намерим работещ текстов модел. Последна грешка: {last_error}"}

    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------- ИНТЕРФЕЙС ----------------
st.set_page_config(page_title="GEO Анализатор Pro", page_icon="🚀", layout="wide")

st.sidebar.header("⚙️ Настройки")
api_key = st.sidebar.text_input("Gemini API Ключ", type="password")
st.sidebar.markdown("[Вземете безплатен ключ от Google AI Studio](https://aistudio.google.com/app/apikey)")
st.sidebar.info("Системата автоматично филтрира и използва най-новия наличен безплатен текстов модел за вашия ключ.")

st.title("🚀 GEO Анализатор & AI Оптимизатор (Gemini)")

if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = None
if 'optimized_result' not in st.session_state:
    st.session_state.optimized_result = None

url_input = st.text_input("URL адрес за анализ:", placeholder="https://example.com")

if st.button("Анализирай", type="primary"):
    if not url_input:
        st.warning("Моля, въведете URL адрес.")
    else:
        if not url_input.startswith(('http://', 'https://')):
            url_input = 'https://' + url_input
            
        with st.spinner("Анализиране на страницата..."):
            st.session_state.analysis_data = analyze_page(url_input)
            st.session_state.optimized_result = None 

if st.session_state.analysis_data:
    data = st.session_state.analysis_data
    if not data['success']:
        st.error(data['error'])
    else:
        st.success("Анализът приключи успешно!")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Общо думи", data['word_count'])
        col2.metric("H1", data['h1_count'])
        col3.metric("H2/H3", data['h2_count'] + data['h3_count'])
        col4.metric("Списъци", data['list_count'])
        col5.metric("Таблици", data['table_count'])

        if data['word_count'] < 50:
            st.warning("⚠️ Внимание: Открит е много малко текст. Ако сайтът използва JavaScript за зареждане на съдържанието, инструментът не може да го извлече пълноценно.")

        st.divider()
        st.subheader("🤖 Автоматична GEO Оптимизация (Gemini)")
        
        if st.button("✨ Оптимизирай текста с AI (Изисква API ключ)", type="secondary"):
            if not api_key:
                st.error("❌ Моля, поставете вашия Gemini API ключ в страничното меню вляво!")
            elif data['word_count'] < 20:
                st.error("❌ Извлеченият текст е прекалено кратък, за да бъде оптимизиран.")
            else:
                with st.spinner("Gemini търси най-добрия модел и преструктурира текста ви... Това може да отнеме около 10-15 секунди."):
                    st.session_state.optimized_result = optimize_content_with_gemini(data['raw_text'], api_key)

        if st.session_state.optimized_result:
            opt_result = st.session_state.optimized_result
            if opt_result['success']:
                st.success("✅ Текстът е успешно оптимизиран!")
                
                with st.container(border=True):
                    st.markdown(opt_result['optimized_text'])
                
                st.download_button(
                    label="📥 Изтегли оптимизирания текст (.md)",
                    data=opt_result['optimized_text'],
                    file_name="geo_optimized_content.md",
                    mime="text/markdown"
                )
            else:
                st.error(f"Грешка при комуникацията с Gemini: {opt_result['error']}")