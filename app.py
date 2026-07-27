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
        
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
            and 'image' not in m.name.lower()
            and 'vision' not in m.name.lower()
            and 'embedding' not in m.name.lower()
        ]
        available_models.sort(reverse=True)
        
        system_instructions = """Ти си експерт по GEO (Generative Engine Optimization). 
Пренапиши предоставения текст, така че да бъде перфектно оптимизиран за AI търсачки.
Правила:
1. BLUF: Най-важният извод/факт да е първото изречение.
2. Структура: Ясни Markdown заглавия (H2, H3).
3. Форматиране: Списъци (bullet points) за характеристики/предимства.
4. Тон: Професионален, обективен.
5. FAQ: В края добави 2-3 въпроса (Често задавани въпроси)."""

        safe_text = text[:30000] 
        full_prompt = system_instructions + "\n\nЕто текста за пренаписване:\n" + safe_text
        last_error = ""
        
        for model_name in available_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(full_prompt)
                return {"success": True, "optimized_text": response.text}
            except Exception as e:
                last_error = str(e)
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
st.sidebar.markdown("[Вземете безплатен ключ от Google](https://aistudio.google.com/app/apikey)")

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

# --- ПОКАЗВАНЕ НА РЕЗУЛТАТИТЕ ---
if st.session_state.analysis_data:
    data = st.session_state.analysis_data
    if not data['success']:
        st.error(data['error'])
    else:
        # Изчисляване на GEO Скор (Рейтинг)
        score = 0
        
        if data['h1_count'] == 1:
            score += 25
            h1_status = "✅ Отлично"
        elif data['h1_count'] > 1:
            score += 10
            h1_status = "⚠️ Нужда от редакция"
        else:
            h1_status = "❌ Критично"

        if data['h2_count'] > 0 or data['h3_count'] > 0:
            score += 25
            h2_status = "✅ Добра структура"
        else:
            h2_status = "❌ Слаба структура"

        if data['has_lists'] or data['has_tables']:
            score += 25
            list_status = "✅ Налични"
        else:
            list_status = "❌ Липсват"

        if 300 <= data['word_count'] <= 4000:
            score += 25
            length_status = "✅ Оптимална"
        else:
            score += 10
            length_status = "⚠️ Неоптимална"

        # 1. ОБЩА ПРИСЪДА
        st.subheader("🎯 Има ли нужда този сайт от оптимизация?")
        if score <= 50:
            st.error(f"**Слаб резултат ({score}/100).** Сайтът има **спешна нужда от оптимизация**. AI търсачките трудно ще разберат съдържанието, защото липсва правилна структура и форматиране.")
        elif score <= 80:
            st.warning(f"**Среден резултат ({score}/100).** Сайтът има **нужда от подобрение**. Има добра основа, но липсват някои ключови GEO елементи, за да бъде лесно цитиран от AI.")
        else:
            st.success(f"**Отличен резултат ({score}/100)!** Сайтът е **много добре подготвен** за AI търсачки. Оптимизация е нужна само ако искате да пренапишете самия текст стилистично.")

        st.divider()

        # 2. ДЕТАЙЛЕН АНАЛИЗ С ОБЯСНЕНИЯ
        st.subheader("📊 Детайлен анализ и обяснения")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**Общо думи: {data['word_count']}** ({length_status})")
            st.caption("ℹ️ *Защо е важно:* AI моделите имат нужда от достатъчно контекст (поне 300 думи), за да разберат експертизата ви. Много кратки или много дълги и разводнени текстове не се класират добре.")
            st.write("")
            st.markdown(f"**H1 Заглавия: {data['h1_count']}** ({h1_status})")
            st.caption("ℹ️ *Защо е важно:* H1 е най-важният ориентир за AI каква е основната тема. Перфектното GEO изисква точно 1 главно заглавие на страница.")
            
        with col2:
            st.markdown(f"**H2 и H3 Подзаглавия: {data['h2_count'] + data['h3_count']}** ({h2_status})")
            st.caption("ℹ️ *Защо е важно:* AI сканира текста подобно на хората. Подзаглавията разделят информацията на логически секции, което улеснява машината да намира конкретни отговори.")
            st.write("")
            st.markdown(f"**Списъци и таблици: {data['list_count']} списъка, {data['table_count']} таблици** ({list_status})")
            st.caption("ℹ️ *Защо е важно:* AI обожава булети (bullet points) и таблици! От тях най-лесно се извличат конкретни факти, характеристики и сравнения, които AI директно цитира.")

        if data['word_count'] < 50:
            st.warning("⚠️ *Техническа бележка: Открит е много малко текст. Това може да означава, че сайтът разчита на JavaScript, който скриптът ни не може да прочете.*")

        st.divider()
        
        # 3. АВТОМАТИЧНА ОПТИМИЗАЦИЯ
        st.subheader("🤖 Пренапиши текста с AI (Gemini)")
        st.write("Дори и сайтът да има висок резултат като структура, AI може да го пренапише стилистично (прилагайки принципа BLUF и добавяйки FAQ секция).")
        
        if st.button("✨ Оптимизирай текста с AI (Изисква API ключ)", type="secondary"):
            if not api_key:
                st.error("❌ Моля, поставете вашия Gemini API ключ в страничното меню вляво!")
            elif data['word_count'] < 20:
                st.error("❌ Извлеченият текст е прекалено кратък.")
            else:
                with st.spinner("Gemini чете и преструктурира текста ви..."):
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
