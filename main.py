import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# 페이지 기본 설정
st.set_page_config(page_title="동네별 인구 피라미드", layout="wide")
st.title("🏘️ 동네별 인구 피라미드 탐색기")

# 1. 데이터 로드 함수
@st.cache_data
def load_data():
    # 깃허브의 CSV 파일을 판다스로 바로 읽기 위해 raw 주소 사용
    url = "https://raw.githubusercontent.com/giwoong729/population/main/population_ts_yearly_gender.zip"
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
    sido_list = df_latest['시도'].dropna().unique()
    selected_sido = st.selectbox("1. 시도 선택", sido_list)

with col2:
    sigungu_list = df_latest[df_latest['시도'] == selected_sido]['시군구'].dropna().unique()
    selected_sigungu = st.selectbox("2. 시군구 선택", sigungu_list)

with col3:
    dong_list = df_latest[
        (df_latest['시도'] == selected_sido) & 
        (df_latest['시군구'] == selected_sigungu)
    ]['동'].dropna().unique()
    selected_dong = st.selectbox("3. 동 선택", dong_list)

# 4. 선택한 동네의 인구 데이터 처리 및 그래프 그리기
if selected_dong:
    # 최종적으로 선택한 동네의 데이터
    target_data = df_latest[
        (df_latest['시도'] == selected_sido) & 
        (df_latest['시군구'] == selected_sigungu) & 
        (df_latest['동'] == selected_dong)
    ]
    
    if not target_data.empty:
        # 0세부터 100세 이상까지의 라벨 리스트 만들기
        age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]
        
        # 남자, 여자 열 이름 리스트
        male_cols = [f"남_{age}" for age in age_labels]
        female_cols = [f"여_{age}" for age in age_labels]
        
        # 남녀 인구수 리스트로 변환
        male_pops = target_data[male_cols].iloc[0].tolist()
        female_pops = target_data[female_cols].iloc[0].tolist()
        
        # -----------------------------------------------------
        # [신규 추가] 지표 계산 로직 (총인구, 평균연령, 고령화율)
        # -----------------------------------------------------
        # 각 나이별 총 인구수 리스트 (남+여)
        total_pops_by_age = [m + f for m, f in zip(male_pops, female_pops)]
        
        # 1) 총인구
        total_pop = sum(total_pops_by_age)
        
        # 2) 평균 연령 계산 (나이 * 해당 나이 인구수 합 / 총인구)
        # '100세 이상'은 계산 편의상 100세로 간주합니다.
        total_age_sum = sum(age * pop for age, pop in enumerate(total_pops_by_age))
        avg_age = total_age_sum / total_pop if total_pop > 0 else 0
        
        # 3) 고령화율 (65세 이상 인구 / 총인구 * 100)
        elderly_pop = sum(total_pops_by_age[65:])  # 인덱스 65부터 끝까지
        youth_pop = sum(total_pops_by_age[:15])    # 유소년(0~14세) 인구, 인덱스 0~14
        aging_rate = (elderly_pop / total_pop * 100) if total_pop > 0 else 0

        # 지표 카드 화면 출력
        st.markdown("---")
        st.subheader(f"📊 {selected_dong} 인구 지표 요약")
        
        metric1, metric2, metric3 = st.columns(3)
        with metric1:
            st.metric("총인구", f"{total_pop:,}명")
        with metric2:
            st.metric("평균연령", f"{avg_age:.1f}세")
        with metric3:
            # 고령화율 20% 초과 시 주의 아이콘 추가
            aging_label = "고령화율 ⚠️" if aging_rate >= 20 else "고령화율"
            st.metric(aging_label, f"{aging_rate:.1f}%")

        st.markdown("---")
        
        # -----------------------------------------------------
        # 인구 피라미드 그래프 그리기
        # -----------------------------------------------------
        male_pops_negative = [-val for val in male_pops]
        
        fig = go.Figure()
        
        # 남성 그래프 (따뜻한 머스터드/오렌지)
        fig.add_trace(go.Bar(
            y=age_labels, x=male_pops_negative, name='남성', orientation='h',
            marker_color='#F4A261', customdata=male_pops,
            hovertemplate="%{y} 남성: %{customdata:,}명<extra></extra>"
        ))
        
        # 여성 그래프 (따뜻한 코랄/다홍)
        fig.add_trace(go.Bar(
            y=age_labels, x=female_pops, name='여성', orientation='h',
            marker_color='#E76F51',
            hovertemplate="%{y} 여성: %{x:,}명<extra></extra>"
        ))
        
        fig.update_layout(
            title=f"<b>{selected_sido} {selected_sigungu} {selected_dong} 인구 구조</b>",
            barmode='relative',
            plot_bgcolor='white',
            legend=dict(x=0.8, y=1.0),
            margin=dict(l=0, r=0, t=50, b=0),
            height=700,
            
            # 세로축(나이) 순서 0세 -> 100세 이상으로 완전 고정
            yaxis=dict(
                categoryorder='array',
                categoryarray=age_labels,
                tickmode='linear',
                dtick=5
            ),
            xaxis=dict(
                title='인구 수 (명)',
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
                zerolinecolor='gray'
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # -----------------------------------------------------
        # [신규 추가] 동네 특성 한 줄 설명
        # -----------------------------------------------------
        st.markdown("### 💡 우리 동네 요약")
        
        if aging_rate >= 20:
            st.info(f"어르신 인구가 20%를 넘는 **초고령화 동네**입니다. 아이들보다 어르신이 훨씬 많은 편이에요.")
        elif youth_pop > elderly_pop:
            st.success(f"어르신보다 아이들(0~14세)이 더 많은 **젊고 활기찬 동네**네요!")
        else:
            st.info(f"아이들보다는 중장년층과 어르신 비중이 더 높은 **성숙한 동네**입니다.")
            
    else:
        st.warning("선택하신 동네의 데이터가 존재하지 않습니다.")
