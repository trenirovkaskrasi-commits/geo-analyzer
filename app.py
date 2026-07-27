import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import time

# ---------------- ФУНКЦИИ ЗА АНАЛИЗ ----------------
def analyze_page(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Извличане на Метаданни
        title = soup.find('title').get_text(strip=True) if soup.find('title') else ""
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        meta_desc = meta_desc_tag['content'].strip() if meta_desc_tag and meta_desc_tag.get('content') else ""
        
        # 2. Извличане на изображения (Alt text)
        images = soup.find_all('img')
        total_images = len(images)
        images_with_alt = sum(1 for img in images if img.get('alt') and img.get('alt').strip() != "")
        
        # Премахване на нежелани елементи за чист текст
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.extract()
            
        # 3. Основно съдържание
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
            'url': url,
            'word_count': word_count,
            'raw_text': " ".join(words), 
            'h1_count': len(h1_tags),
            'h2_count': len(h2_tags),
            'h3_count': len(h3_tags),
            'has_lists': len(lists) > 0,
            'has_tables': len(tables) > 0,
            'list_count': len(lists),
            'table_count': len(tables),
            'title': title,
            'meta_desc': meta_desc,
            'total_images': total_images,
            'images_with_alt': images_with_alt
        }
        
    except Exception as e:
        return {'success': False, 'url': url, 'error': f"Грешка: {str(e)}"}

def calculate_geo_score(data):
    score = 0
    
    # H1 Заглавие (Макс 20)
    if data['h1_count'] == 1: score += 20
    elif data['h1_count'] > 1: score += 10
    
    # Подзаглавия (Макс 20)
    if data['h2_count'] > 0 or data['h3_count'] > 0: score += 20
    
    # Списъци/Таблици (Макс 20)
    if data['has_lists'] or data['has_tables']: score += 20
    
    # Метаданни (Макс 15)
    if 10 < len(data['title']) < 80: score += 10
    if 50 < len(data['meta_desc']) < 200: score += 5
    
    # Изображения (Макс 10)
    if data['total_images'] == 0:
        score += 10 # Ако няма изображения, не наказваме
    else:
        alt_ratio = data['images_with_alt'] / data['total_images']
        if alt_ratio >= 0.9: score += 10
        elif alt_ratio >= 0.5: score += 5
        
    # Дължина (Макс 15)
    if 300 <= data['word_count'] <= 4000: score += 15
    elif data['word_count'] > 50: score += 5
    
    return score

# ---------------- ФУНКЦИИ ЗА SITEMAP И AI ----------------
def extract_sitemap_urls(sitemap_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(sitemap_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'xml') # Парсираме XML
        urls = [loc.text for loc in soup.find_all('loc') if "http" in loc.text]
        return urls
    except Exception as e:
        return []

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
        
        system_instructions = """Ти си експерт по GEO. Пренапиши текста за AI търсачки.
Правила: 1. BLUF в началото. 2. Markdown H2/H3. 3. Списъци. 4. Професионален тон. 5. FAQ накрая."""

        full_prompt = system_instructions + "\n\nТекст:\n" + text[:30000] 
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
                return {"success": False, "error": last_error}
                    
        return {"success": False, "error": f"Грешка с модела. {last_error}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def show_detailed_analysis(data, score):
    col1, col2, col3 = st.columns(3)
    col1.metric("Общо думи", data['word_count'])
    col2.metric("H1 Заглавия", data['h1_count'])
    col3.metric("H2/H3", data['h2_count'] + data['h3_count'])
    
    col4, col5, col6 = st.columns(3)
    col4.metric("Списъци", data['list_count'])
    col5.metric("Снимки без Alt", data['total_images'] - data['images_with_alt'])
    col6.metric("GEO Score", f"{score}/100")

    st.markdown("### 📝 Обяснения на метриките:")
    
    st.markdown(f"**1. Мета заглавие (Title):** `{data['title'] if data['title'] else 'Липсва'}`")
    st.caption("ℹ️ *Защо е важно:* AI моделите четат заглавието на страницата, за да разберат контекста. То трябва да бъде ясно и точно (между 10 и 80 символа).")
    
    h1_msg = "✅ Точно 1 заглавие" if data['h1_count'] == 1 else ("❌ Липсва" if data['h1_count'] == 0 else "⚠️ Твърде много H1")
    st.markdown(f"**2. Главно заглавие (H1):** {h1_msg}")
    st.caption("ℹ️ *Защо е важно:* H1 заглавието е темата на страницата. Търсачките се объркват, ако има повече от едно главно заглавие.")
    
    list_msg = "✅ Открити са списъци" if data['has_lists'] else "❌ Липсват списъци"
    st.markdown(f"**3. Структурирани данни (Списъци):** {list_msg}")
    st.caption("ℹ️ *Защо е важно:* Булетите (списъците) са любимият формат на AI. От тях изкуственият интелект извлича конкретни факти.")
    
    st.markdown(f"**4. Изображения (Alt Text):** Намерени {data['total_images']}, от които {data['images_with_alt']} имат описание.")
    st.caption("ℹ️ *Защо е важно:* Машините не виждат картинки, те четат Alt текста. Липсата му означава пропусната ключова дума.")

# ---------------- ИНТЕРФЕЙС ----------------
st.set_page_config(page_title="GEO Analyzer Dashboard", page_icon="📈", layout="wide")

st.sidebar.header("⚙️ Настройки и AI")
api_key = st.sidebar.text_input("Gemini API Ключ", type="password")
st.sidebar.markdown("[Вземете ключ от тук](https://aistudio.google.com/app/apikey)")

st.title("📈 GEO Analyzer Dashboard")
st.markdown("Пълен набор инструменти за оптимизация на сайтове за Generative AI търсачки.")

# Създаване на табове
tab_single, tab_battle, tab_sitemap = st.tabs(["🔍 Единичен Анализ", "⚔️ Битка с Конкурент", "🗺️ Масов Анализ (Sitemap)"])

# ================= ТАБ 1: ЕДИНИЧЕН АНАЛИЗ =================
with tab_single:
    url_single = st.text_input("Въведете URL адрес:", placeholder="https://example.com/page", key="url_single")
    
    if st.button("Анализирай Страница", type="primary"):
        if url_single:
            with st.spinner("Анализиране..."):
                data = analyze_page(url_single)
                if not data['success']:
                    st.error(data['error'])
                else:
                    score = calculate_geo_score(data)
                    st.session_state['single_data'] = data
                    st.session_state['single_score'] = score
                    st.session_state['opt_result'] = None

    if 'single_data' in st.session_state and st.session_state['single_data']['url'] == url_single:
        data = st.session_state['single_data']
        score = st.session_state['single_score']
        
        if score <= 50: st.error(f"**GEO SCORE: {score}/100** (Спешна нужда от оптимизация)")
        elif score <= 80: st.warning(f"**GEO SCORE: {score}/100** (Нужда от подобрение)")
        else: st.success(f"**GEO SCORE: {score}/100** (Отлично оптимизирано)")
        
        show_detailed_analysis(data, score)
        
        st.divider()
        st.markdown("### 🤖 Автоматична GEO Оптимизация (Gemini)")
        if st.button("✨ Пренапиши текста", type="secondary"):
            if not api_key:
                st.error("❌ Моля, въведете Gemini API Ключ в лявото меню!")
            elif data['word_count'] < 20:
                st.error("❌ Текстът е прекалено кратък.")
            else:
                with st.spinner("Изкуственият интелект пренаписва текста..."):
                    st.session_state['opt_result'] = optimize_content_with_gemini(data['raw_text'], api_key)
        
        if 'opt_result' in st.session_state and st.session_state['opt_result']:
            res = st.session_state['opt_result']
            if res['success']:
                st.success("Готово!")
                with st.container(border=True):
                    st.markdown(res['optimized_text'])
                
                # ВЪРНАТ БУТОН ЗА ИЗТЕГЛЯНЕ
                st.download_button(
                    label="📥 Изтегли оптимизирания текст (.md)",
                    data=res['optimized_text'],
                    file_name="geo_optimized_content.md",
                    mime="text/markdown"
                )
            else:
                st.error(res['error'])

# ================= ТАБ 2: БИТКА С КОНКУРЕНТ =================
with tab_battle:
    st.markdown("Сравнете вашия сайт с този на конкурент, за да видите кой е по-удобен за AI търсачките.")
    colA, colB = st.columns(2)
    url_mine = colA.text_input("Вашият URL:", placeholder="https://my-site.com")
    url_comp = colB.text_input("Конкурентен URL:", placeholder="https://competitor.com")
    
    if st.button("⚔️ Започни битката", type="primary"):
        if url_mine and url_comp:
            with st.spinner("Анализиране на двата сайта..."):
                data_mine = analyze_page(url_mine)
                data_comp = analyze_page(url_comp)
                
                if data_mine['success'] and data_comp['success']:
                    score_mine = calculate_geo_score(data_mine)
                    score_comp = calculate_geo_score(data_comp)
                    
                    st.markdown("### 🏆 Резултати")
                    if score_mine > score_comp:
                        st.success(f"**ПОБЕДА!** Вашият сайт ({score_mine} т.) победи конкурента ({score_comp} т.).")
                    elif score_comp > score_mine:
                        st.error(f"**ЗАГУБА!** Конкурентът ({score_comp} т.) има по-добро GEO от вас ({score_mine} т.).")
                    else:
                        st.info(f"**РАВЕНСТВО!** И двата сайта имат {score_mine} т.")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("#### Вашият сайт")
                        st.metric("GEO Скор", score_mine)
                        st.write(f"- H1 Заглавия: {data_mine['h1_count']}")
                        st.write(f"- H2/H3 Заглавия: {data_mine['h2_count'] + data_mine['h3_count']}")
                        st.write(f"- Списъци: {data_mine['list_count']}")
                        st.write(f"- Снимки без Alt: {data_mine['total_images'] - data_mine['images_with_alt']}")
                    with c2:
                        st.markdown("#### Конкурент")
                        st.metric("GEO Скор", score_comp)
                        st.write(f"- H1 Заглавия: {data_comp['h1_count']}")
                        st.write(f"- H2/H3 Заглавия: {data_comp['h2_count'] + data_comp['h3_count']}")
                        st.write(f"- Списъци: {data_comp['list_count']}")
                        st.write(f"- Снимки без Alt: {data_comp['total_images'] - data_comp['images_with_alt']}")
                else:
                    st.error("Грешка при сканирането на един от сайтовете.")

# ================= ТАБ 3: SITEMAP МАСОВ АНАЛИЗ =================
with tab_sitemap:
    st.markdown("Сканирайте цял Sitemap, за да откриете страниците с най-слаб GEO Скор.")
    sitemap_url = st.text_input("Sitemap URL:", placeholder="https://example.com/sitemap.xml")
    max_urls = st.slider("Максимум страници за сканиране:", min_value=5, max_value=50, value=20)
    
    if st.button("🗺️ Сканирай Sitemap", type="primary"):
        if sitemap_url:
            with st.spinner("Извличане на URL адреси от Sitemap..."):
                urls = extract_sitemap_urls(sitemap_url)
                
            if not urls:
                st.error("Не успяхме да намерим валидни линкове в този Sitemap (или достъпът е блокиран).")
            else:
                st.info(f"Намерени са общо {len(urls)} линка. Сканиране на първите {max_urls}...")
                urls_to_scan = urls[:max_urls]
                
                results = []
                progress_bar = st.progress(0)
                
                for i, u in enumerate(urls_to_scan):
                    data = analyze_page(u)
                    if data['success']:
                        score = calculate_geo_score(data)
                        results.append({
                            "URL": u,
                            "GEO Score": score,
                            "H1": data['h1_count'],
                            "Думи": data['word_count'],
                            "Списъци": data['list_count']
                        })
                    progress_bar.progress((i + 1) / len(urls_to_scan))
                    time.sleep(0.5) 
                
                if results:
                    st.success("Сканирането завърши!")
                    df = pd.DataFrame(results)
                    df = df.sort_values(by="GEO Score", ascending=True)
                    st.dataframe(df, use_container_width=True)
                    st.caption("💡 Таблицата е сортирана от най-ниския резултат нагоре. Започнете оптимизацията от първите страници в списъка.")
