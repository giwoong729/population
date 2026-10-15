import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# 페이지 기본 설정
st.set_page_config(page_title="동네별 인구 피라미드", layout="wide")
st.title("🏘️ 동네별 인구 피라미드 탐색기")

# 1. 데이터 로드 함수 (캐싱을 사용하여 매번 다운로드하지 않도록 속도 향상)
@st.cache_data
def load_data():
    # 깃허브의 CSV 파일을 판다스로 바로 읽기 위해 raw 주소 사용
    url = "https://raw.githubusercontent.com/giwoong729/population/main/population_ts_yearly_gender.zip"
    # zip 파일 안의 csv를 pandas가 바로 읽어옵니다. (한글 깨짐 방지를 위해 cp949/utf-8 예외처리)
    try:
        df = pd.read_csv(url, compression='zip', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(url, compression='zip', encoding='cp949')
    return df

# 데이터 불러오기
with st.spinner("데이터를 불러오는 중입니다..."):
    df = load_data()

# 2. 최신 연도 데이터만 골라내기
latest_year = df['연도'].max()
df_latest = df[df['연도'] == latest_year]

st.write(f"**기준 연도:** {latest_year}년")

# 3. 화면 UI: 시도 -> 시군구 -> 동 드롭다운 생성 (가로로 3등분 배치)
col1, col2, col3 = st.columns(3)

with col1:
    # 시도 목록을 중복 없이 가져와 선택상자 생성
    sido_list = df_latest['시도'].dropna().unique()
    selected_sido = st.selectbox("1. 시도 선택", sido_list)

with col2:
    # 선택된 시도에 해당하는 시군구 목록만 필터링
    sigungu_list = df_latest[df_latest['시도'] == selected_sido]['시군구'].dropna().unique()
    selected_sigungu = st.selectbox("2. 시군구 선택", sigungu_list)

with col3:
    # 선택된 시도와 시군구에 해당하는 동 목록만 필터링
    dong_list = df_latest[
        (df_latest['시도'] == selected_sido) & 
        (df_latest['시군구'] == selected_sigungu)
    ]['동'].dropna().unique()
    selected_dong = st.selectbox("3. 동 선택", dong_list)

# 4. 선택한 동네의 인구 피라미드 그리기
if selected_dong:
    # 최종적으로 선택한 동네의 데이터 한 줄만 가져오기
    target_data = df_latest[
        (df_latest['시도'] == selected_sido) & 
        (df_latest['시군구'] == selected_sigungu) & 
        (df_latest['동'] == selected_dong)
    ]
    
    # 데이터가 존재하는지 확인
    if not target_data.empty:
        # 0세부터 100세 이상까지의 라벨 리스트 만들기
        age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]
        
        # 남자, 여자 열 이름 리스트 만들기 ('남_0세', '여_0세' 형식)
        male_cols = [f"남_{age}" for age in age_labels]
        female_cols = [f"여_{age}" for age in age_labels]
        
        # 데이터프레임에서 값만 추출하여 리스트로 변환 (iloc[0]을 사용해 첫 번째 행 추출)
        male_pops = target_data[male_cols].iloc[0].tolist()
        female_pops = target_data[female_cols].iloc[0].tolist()
        
        # 남자는 왼쪽으로 그래프를 그려야 하므로 음수(-)로 변환
        male_pops_negative = [-val for val in male_pops]
        
        # 5. Plotly 가로 막대그래프(피라미드) 설정
        fig = go.Figure()
        
        # 남성 막대그래프 추가 (따뜻한 머스터드/오렌지 톤)
        fig.add_trace(go.Bar(
            y=age_labels,
            x=male_pops_negative,
            name='남성',
            orientation='h',
            marker_color='#F4A261', 
            customdata=male_pops, # 마우스를 올렸을 때(hover) 보여줄 원래 양수 값
            hovertemplate="%{y} 남성: %{customdata:,}명<extra></extra>"
        ))
        
        # 여성 막대그래프 추가 (따뜻한 코랄/다홍 톤)
        fig.add_trace(go.Bar(
            y=age_labels,
            x=female_pops,
            name='여성',
            orientation='h',
            marker_color='#E76F51',
            hovertemplate="%{y} 여성: %{x:,}명<extra></extra>"
        ))
        
        # 6. 레이아웃 세부 설정 (요청하신 축 고정 옵션 적용)
        fig.update_layout(
            title=f"{selected_sido} {selected_sigungu} {selected_dong} 인구 구조",
            barmode='relative',     # 남녀 막대가 중앙을 기준으로 양옆으로 퍼지게 함
            plot_bgcolor='white',   # 배경색을 깔끔하게 하얀색으로
            legend=dict(x=0.8, y=1.0),
            margin=dict(l=0, r=0, t=50, b=0),
            height=700,             # 나이대가 많으므로 그래프 세로 길이를 넉넉히 줌
            
            # ★ 세로축(나이) 설정 ★
            yaxis=dict(
                categoryorder='array',       # 배열에 정의된 순서만을 엄격히 따르도록 설정
                categoryarray=age_labels,    # 0세부터 100세 이상까지 순서대로 리스트 직접 주입 (맨 아래가 0세)
                tickmode='linear',           # 모든 나이 눈금이 골고루 보이도록 설정
                dtick=5                      # 너무 빽빽해지지 않게 5세 단위로 눈금 표시
            ),
            # 가로축(인구 수) 설정
            xaxis=dict(
                title='인구 수 (명)',
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
                zerolinecolor='gray'
            )
        )
        
        # 화면에 그래프 출력
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("선택하신 동네의 데이터가 존재하지 않습니다.")
