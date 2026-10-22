import datetime
import pandas as pd
import requests
import streamlit as st


# ---------------------------------------------------------
# 1. 페이지 기본 설정 및 타이틀
# ---------------------------------------------------------
st.set_page_config(
    page_title="일별 박스오피스 조회", page_icon="🎬", layout="wide"
)

st.title("🎬 일별 박스오피스 순위")


# ---------------------------------------------------------
# 2. 한국 시간(UTC+9) 기준 어제 날짜 계산
# ---------------------------------------------------------
def get_max_selectable_date_kst():
    """배포 서버의 시계와 상관없이 한국 시간(UTC+9) 기준 어제 날짜(date 객체)를 반환합니다."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    kst_now = utc_now + datetime.timedelta(hours=9)
    yesterday_kst = kst_now - datetime.timedelta(days=1)
    return yesterday_kst.date()


# 고를 수 있는 가장 늦은 날짜(어제)
max_date = get_max_selectable_date_kst()

# 달력 widget을 통해 사용자가 원하는 조회 날짜 선택 (기본값: 어제)
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요 (최대 선택 가능: 어제)",
    value=max_date,
    max_value=max_date,
    help="오늘 날짜는 아직 집계 전이므로 어제 날짜까지만 선택 가능합니다.",
)

# API 요청에 맞게 YYYYMMDD 포맷으로 변환
target_dt = selected_date.strftime("%Y%m%d")


# ---------------------------------------------------------
# 3. KOBIS API 데이터 호출 및 예외 처리
# ---------------------------------------------------------
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info(
        "**[확인 사항]**\n"
        "- Streamlit Cloud의 `Secrets` 설정 또는 로컬 `.streamlit/secrets.toml` 파일에 "
        "`KOBIS_KEY = '발급받은_키'` 형태로 등록되어 있는지 확인해 주세요."
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if "faultInfo" in data:
        error_msg = data["faultInfo"].get("message", "알 수 없는 오류")
        st.error("⚠️ API 키 인증에 실패했거나 요청 오류가 발생했습니다.")
        st.warning(f"오류 상세 내용: {error_msg}")
        st.info(
            "**[확인 사항]**\n"
            "1. Secrets에 입력한 `KOBIS_KEY`가 KOBIS 공식 홈페이지에서 발급받은 키와 일치하는지 확인해 주세요.\n"
            "2. 일일 API 사용량이 초과되지 않았는지 확인해 주세요."
        )
        st.stop()

    box_office_result = data.get("boxOfficeResult", {})
    daily_list = box_office_result.get("dailyBoxOfficeList", [])

    # 선택한 날짜의 데이터가 비어 있는 경우 안내 문구 출력
    if not daily_list:
        st.warning("⚠️ 그날은 아직 집계 전입니다.")
        st.info(
            f"**[확인 사항]**\n"
            f"- 선택하신 날짜({selected_date.strftime('%Y-%m-%d')})의 집계가 아직 완료되지 않았거나 데이터가 제공되지 않는 일자입니다."
        )
        st.stop()

except requests.exceptions.RequestException as e:
    st.error("🌐 네트워크 연결 또는 KOBIS 서버 요청에 실패했습니다.")
    st.warning(f"상세 에러: {e}")
    st.info(
        "**[확인 사항]**\n"
        "1. 인터넷 연결 상태를 확인해 주세요.\n"
        "2. KOBIS 서버가 일시적인 점검 중인지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 4. 데이터 전처리 (숫자 변환 및 이모지/화살표 가공)
# ---------------------------------------------------------
df = pd.DataFrame(daily_list)

# 숫자로 가공할 컬럼 변환
numeric_cols = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)


# 전날 대비 순위 증감(rankInten) 화살표 가공 함수
def format_rank_inten(val):
    if val > 0:
        return f"🔺 {val}"  # 빨간 위 화살표 (순위 상승)
    elif val < 0:
        return f"🔹 {abs(val)}"  # 파란 아래 화살표 (순위 하강)
    else:
        return "-"  # 변동 없음


# 누적관객(audiAcc) 100만 이상 시 영화명에 트로피 이모지 🏆 추가 함수
def format_movie_name(row):
    movie_name = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"🏆 {movie_name}"
    return movie_name


df["rankIntenDisplay"] = df["rankInten"].apply(format_rank_inten)
df["movieNmDisplay"] = df.apply(format_movie_name, axis=1)

st.caption(
    f"🗓️ 조회 기준 날짜: **{selected_date.strftime('%Y년 %m월 %d일')}**"
)


# ---------------------------------------------------------
# 5. 1위 영화 하이라이트 (지표 카드 3장)
# ---------------------------------------------------------
top_movie = df.iloc[0]

st.subheader(f"🥇 1위: {top_movie['movieNmDisplay']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="일일 관객수",
        value=f"{top_movie['audiCnt']:,} 명",
        delta=f"전날 대비 순위: {top_movie['rankIntenDisplay']}",
    )

with col2:
    st.metric(label="누적 관객수", value=f"{top_movie['audiAcc']:,} 명")

with col3:
    st.metric(label="스크린수", value=f"{top_movie['scrnCnt']:,} 개")

st.markdown("---")


# ---------------------------------------------------------
# 6. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 TOP 5")

top5_df = df.head(5)
st.bar_chart(data=top5_df, x="movieNm", y="audiCnt", color="#FF4B4B")

st.markdown("---")


# ---------------------------------------------------------
# 7. 전체 박스오피스 순위 표 (1~10위)
# ---------------------------------------------------------
st.subheader("📋 전체 박스오피스 순위")

display_df = df[
    [
        "rank",
        "rankIntenDisplay",
        "movieNmDisplay",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()

display_df.columns = [
    "순위",
    "순위증감",
    "영화명",
    "개봉일",
    "관객수(명)",
    "누적관객(명)",
    "스크린수",
]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "관객수(명)": st.column_config.NumberColumn(format="%d명"),
        "누적관객(명)": st.column_config.NumberColumn(format="%d명"),
        "스크린수": st.column_config.NumberColumn(format="%d개"),
    },
)
