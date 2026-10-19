import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# 페이지 기본 설정
st.set_page_config(page_title="전국 인구 단계구분도", layout="wide")
st.title("🗺️ 전국 시군구별 인구 비율 지도")

# 1. 데이터 로드 및 전처리 함수 (캐싱)
@st.cache_data
def load_and_preprocess_data():
    # 1-1. GeoJSON 로드
    geojson_url = "https://raw.githubusercontent.com/first2022-cyber/contents/main/sigungu_kr.geojson"
    geojson_data = requests.get(geojson_url).json()

    # 1-2. 인구 CSV 데이터 로드
    csv_url = "https://raw.githubusercontent.com/first2022-cyber/contents/main/population_ts_yearly_gender.zip"
    try:
        df = pd.read_csv(csv_url, compression='zip', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(csv_url, compression='zip', encoding='cp949')
        
    # 1-3. 시군구 코드(앞 5자리) 추출 및 행정구역 개편 코드 보정
    df['시군구_코드'] = df['코드'].astype(str).str[:5]
    
    def fix_code(code):
        if code == '47720': return '27720'             # 군위군 (경북 -> 대구)
        if code.startswith('42'): return '51' + code[2:] # 강원 -> 강원특별자치도
        if code.startswith('45'): return '52' + code[2:] # 전북 -> 전북특별자치도
        return code
    
    df['시군구_코드'] = df['시군구_코드'].apply(fix_code)
    
    # 1-4. 시도 이름 보정 (UI 필터링용)
    def fix_sido(row):
        c = row['시군구_코드']
        if c == '27720': return '대구광역시'
        if c.startswith('51'): return '강원특별자치도'
        if c.startswith('52'): return '전북특별자치도'
        return row['시도']
        
    df['시도'] = df.apply(fix_sido, axis=1)

    # 1-5. 인구수 합산 (전체, 고령 65세 이상, 유소년 0~14세)
    total_cols = [col for col in df.columns if str(col).startswith('계_')]
    elderly_cols = [f"계_{i}세" for i in range(65, 100)] + ['계_100세 이상']
    youth_cols = [f"계_{i}세" for i in range(15)]
    
    df['동별_총인구'] = df[total_cols].sum(axis=1)
    df['동별_고령인구'] = df[elderly_cols].sum(axis=1)
    df['동별_유소년인구'] = df[youth_cols].sum(axis=1)

    return df, geojson_data

# 데이터 불러오기
with st.spinner("데이터와 지도를 불러오는 중입니다..."):
    df_base, geojson_data = load_and_preprocess_data()

# 2. 화면 상단 UI 컨트롤러 (3등분)
col1, col2, col3 = st.columns(3)
with col1:
    selected_year = st.slider("📅 연도 선택", min_value=2015, max_value=2026, value=2026)
with col2:
    metric_choice = st.selectbox("📊 지표 선택", ["고령화율 (%)", "유소년율 (%)"])
with col3:
    sido_list = ["전국"] + sorted(df_base['시도'].dropna().unique().tolist())
    selected_sido = st.selectbox("📍 지역(시도) 확대", sido_list)

# 3. 선택한 연도 기준으로 데이터 필터링 및 시군구 단위 합산
df_year = df_base[df_base['연도'] == selected_year]
df_sigungu = df_year.groupby(['시군구_코드', '시도', '시군구']).agg(
    총인구=('동별_총인구', 'sum'),
    고령인구=('동별_고령인구', 'sum'),
    유소년인구=('동별_유소년인구', 'sum')
).reset_index()

# 비율 계산
df_sigungu['고령화율 (%)'] = (df_sigungu['고령인구'] / df_sigungu['총인구'] * 100).round(2)
df_sigungu['유소년율 (%)'] = (df_sigungu['유소년인구'] / df_sigungu['총인구'] * 100).round(2)

# 4. 지도 색상 단계(Binning) 고정 로직
# 선택한 지표에 따라 동일한 색상 구간을 유지하여 연도별 비교가 가능하게 만듭니다.
if metric_choice == "고령화율 (%)":
    target_col = '고령화율 (%)'
    bins = [0, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19~23%", "23~28%", "28~38%", "38% 이상"]
    color_map = {"19% 미만": "#fee5d9", "19~23%": "#fcae91", "23~28%": "#fb6a4a", "28~38%": "#de2d26", "38% 이상": "#a50f15"}
else:
    target_col = '유소년율 (%)'
    bins = [0, 7, 9, 11, 13, 100] # 유소년율에 맞춘 별도 구간
    labels = ["7% 미만", "7~9%", "9~11%", "11~13%", "13% 이상"]
    color_map = {"7% 미만": "#eff3ff", "7~9%": "#bdd7e7", "9~11%": "#6baed6", "11~13%": "#3182bd", "13% 이상": "#08519c"}

# 각 지역이 어느 구간(단계)에 속하는지 라벨링
df_sigungu['단계'] = pd.cut(df_sigungu[target_col], bins=bins, labels=labels, right=False)

# 5. 전국/지역구분 지표 계산 (상단 지표 카드용)
nat_total = df_sigungu['총인구'].sum()
nat_target = df_sigungu['고령인구'].sum() if metric_choice == "고령화율 (%)" else df_sigungu['유소년인구'].sum()
nat_rate = (nat_target / nat_total * 100) if nat_total > 0 else 0

# 전국 또는 선택된 시도의 데이터에서 최고/최저 찾기
map_df = df_sigungu if selected_sido == "전국" else df_sigungu[df_sigungu['시도'] == selected_sido]

if not map_df.empty:
    max_row = map_df.loc[map_df[target_col].idxmax()]
    min_row = map_df.loc[map_df[target_col].idxmin()]

    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    with m1:
        prefix = "🇰🇷 전국" if selected_sido == "전국" else f"📍 {selected_sido}"
        st.metric(f"{prefix} 평균 {metric_choice.split(' ')[0]}", f"{nat_rate:.1f}%")
    with m2:
        st.metric(f"📈 가장 높은 시군구", f"{max_row['시도']} {max_row['시군구']}", f"{max_row[target_col]}%")
    with m3:
        st.metric(f"📉 가장 낮은 시군구", f"{min_row['시도']} {min_row['시군구']}", f"{min_row[target_col]}%")
    st.markdown("---")

    # 6. Plotly 단계구분도 그리기
    fig = px.choropleth(
        map_df,
        geojson=geojson_data,
        locations='시군구_코드',
        featureidkey='properties.코드',
        color='단계',
        color_discrete_map=color_map,
        category_orders={"단계": labels},
        hover_name='시군구',
        hover_data={
            '시군구_코드': False,
            '단계': False,
            '시도': True,
            target_col: ':.1f',
            '총인구': ':,.0f'
        }
    )

    # 배경 숨김 및 지역 확대 핏(fit)
    fig.update_geos(
        fitbounds="locations", 
        visible=False
    )
    
    fig.update_layout(
        margin={"r":0, "t":0, "l":0, "b":0},
        height=700,
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend_title_text='비율 구간'
    )

    st.plotly_chart(fig, use_container_width=True)

    # 7. 경계 파일과 맞지 않는 지역 안내 (지도 하단)
    geojson_codes = [f['properties']['코드'] for f in geojson_data['features']]
    unmatched = map_df[~map_df['시군구_코드'].isin(geojson_codes)]
    
    if not unmatched.empty:
        missing_names = unmatched['시도'] + " " + unmatched['시군구']
        st.caption(f"⚠️ **경계 파일과 코드가 일치하지 않아(행정구역 개편 등) 지도에 회색으로 남거나 표시되지 않는 지역이 있습니다:**  \n{', '.join(missing_names.unique())}")
else:
    st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")
