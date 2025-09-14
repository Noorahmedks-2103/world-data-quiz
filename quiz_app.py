import streamlit as st
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# ---------------------------
# MOBILE-FRIENDLY CSS
# ---------------------------
st.markdown(
    """
    <style>
    .css-1d391kg {display: flex; flex-direction: column; align-items: center;}
    div[role="radiogroup"] label { font-size: 20px; padding: 10px 0;}
    .timer { font-size: 22px; font-weight: bold; margin-bottom: 10px; }
    button[kind="secondary"] { padding: 12px 20px !important; font-size: 18px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# CONFIG: Google Sheets Setup
# ---------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSHsnW8a2k50iqPbKdItI8Qukr9pobP1byaqO0s8qnfVPPDCQEkyBQLQ6KUHm6vWdIMwKuljBTGFYCk/pubhtml?gid=0&single=true"

def authenticate_google_sheets():
    creds_json = st.secrets["gcp_service_account"]["creds"]
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    return sheet

# ---------------------------
# Google Sheets Functions
# ---------------------------
def save_score(name, score, total):
    sheet = authenticate_google_sheets()
    percentage = round((score / total) * 100, 2)
    sheet.append_row([name, score, total, percentage])

def load_leaderboard():
    sheet = authenticate_google_sheets()
    data = sheet.get_all_records()
    if data:
        return pd.DataFrame(data)
    else:
        return pd.DataFrame(columns=["Name", "Score", "Total", "Percentage"])

# ---------------------------
# Plotly Global Ranking Chart
# ---------------------------
def show_leaderboard_chart(top_players_df):
    if top_players_df.empty:
        st.write("No scores yet. Be the first to play!")
        return

    fig = px.bar(
        top_players_df[::-1],
        x="Score",
        y="Name",
        orientation='h',
        text="Score",
        color="Percentage",
        color_continuous_scale="Viridis",
        labels={"Score": "Score", "Name": "Player", "Percentage": "Percentage %"}
    )
    fig.update_layout(
        xaxis=dict(range=[0, top_players_df["Score"].max() + 1]),
        margin=dict(l=50, r=50, t=50, b=50),
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# Load Quiz Questions
# ---------------------------
@st.cache_data
def load_questions():
    df = pd.read_csv("questions.csv")
    return df.to_dict(orient="records")

# ---------------------------
# Helper: Random Color
# ---------------------------
def random_color():
    r = random.randint(150, 255)
    g = random.randint(150, 255)
    b = random.randint(150, 255)
    return f'rgb({r},{g},{b})'

# ---------------------------
# Main Quiz App
# ---------------------------
def run_quiz():
    st.title("🌍 World Data Quiz")
    st.write("Test your knowledge of world geography, culture, and data!")

    # Auto-refresh every 5 seconds (optional)
    st_autorefresh(interval=5000, limit=None, key="quiz_autorefresh")

    # Player Name Input (session_state-safe)
    if "player_name" not in st.session_state:
        st.session_state.player_name = st.text_input("Enter your name to start:")

    if not st.session_state.player_name:
        st.warning("Please enter your name to play.")
        return

    # Load and Shuffle Questions
    questions = load_questions()
    if "shuffled_questions" not in st.session_state:
        st.session_state.shuffled_questions = random.sample(questions, len(questions))
        st.session_state.current_q = 0
        st.session_state.score = 0
        st.session_state.colors = [random_color() for _ in range(5)]

    q_index = st.session_state.current_q

    # Show progress bar
    progress = (q_index / len(st.session_state.shuffled_questions))
    st.progress(progress)
    st.caption(f"Question {q_index + 1} of {len(st.session_state.shuffled_questions)}")

    # ---------------------------
    # Quiz Question
    # ---------------------------
    if q_index < len(st.session_state.shuffled_questions):
        q = st.session_state.shuffled_questions[q_index]
        st.subheader(q["question"])

        options = q["options"].split(";")
        answer_key = f"answer_{q_index}"
        if answer_key not in st.session_state:
            st.session_state[answer_key] = None

        selected_answer = st.radio("Choose your answer:", options, key=answer_key)

        # Non-blocking timer
        time_limit = 15
        if f"timer_{q_index}" not in st.session_state:
            st.session_state[f"timer_{q_index}"] = time_limit
            st.session_state[f"timer_start_{q_index}"] = time.time()

        elapsed = int(time.time() - st.session_state[f"timer_start_{q_index}"])
        remaining = max(time_limit - elapsed, 0)
        color = "red" if remaining <= 5 else "black"
        st.markdown(
            f"<div class='timer' style='color:{color}'>⏱️ Time left: <b>{remaining} sec</b></div>",
            unsafe_allow_html=True
        )

        # Auto-submit if time is up
        if remaining == 0:
            if st.session_state[answer_key] == q["answer"]:
                st.success("✅ Correct!")
                st.balloons()
                st.session_state.score += 1
            else:
                st.error(f"❌ Time’s up! Correct answer: {q['answer']}")

            # Save score immediately
            save_score(st.session_state.player_name, st.session_state.score, q_index + 1)

            # Increment question
            st.session_state.current_q += 1
            st.experimental_rerun()

        # Manual Submit Button
        if st.button("Submit Answer"):
            if st.session_state[answer_key] == q["answer"]:
                st.success("✅ Correct!")
                st.balloons()
                st.session_state.score += 1
            else:
                st.error(f"❌ Wrong! Correct answer: {q['answer']}")

            save_score(st.session_state.player_name, st.session_state.score, q_index + 1)
            st.session_state.current_q += 1
            st.experimental_rerun()

        # Dynamic Top 5 leaderboard
        st.subheader("🏆 Top 5 Players So Far")
        leaderboard = load_leaderboard()
        leaderboard = leaderboard.sort_values(by=["Score", "Percentage"], ascending=[False, False])
        top5 = leaderboard.head(5)

        if not top5.empty:
            for i, row in enumerate(top5.itertuples(), 1):
                crown = " 👑" if i == 1 else ""
                color = st.session_state.colors[i-1] if i-1 < len(st.session_state.colors) else random_color()
                st.markdown(
                    f"""
                    <div style='background-color:{color};padding:12px;border-radius:12px;margin-bottom:6px;
                    box-shadow: 2px 2px 8px rgba(0,0,0,0.1);'>
                        <b>#{i} {row.Name}{crown}</b><br>
                        Score: {row.Score} / {row.Total} &nbsp; | &nbsp; Percentage: {row.Percentage}%
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Show chart
        st.subheader("📊 Top Players - Visual Ranking")
        show_leaderboard_chart(top5)

    # ---------------------------
    # Quiz Completed
    # ---------------------------
    else:
        st.balloons()
        st.audio("cheer.mp3", format="audio/mp3")
        st.success("🎉 Quiz Completed!")
        total = len(st.session_state.shuffled_questions)
        score = st.session_state.score
        percentage = round((score / total) * 100, 2)

        st.write(f"**Your Score:** {score}/{total}")
        st.write(f"**Percentage:** {percentage}%")

        # Final leaderboard
        leaderboard = load_leaderboard()
        leaderboard = leaderboard.sort_values(by=["Score", "Percentage"], ascending=[False, False])
        top5 = leaderboard.head(5)

        if not top5.empty:
            for i, row in enumerate(top5.itertuples(), 1):
                crown = " 👑" if i == 1 else ""
                color = st.session_state.colors[i-1] if i-1 < len(st.session_state.colors) else random_color()
                st.markdown(
                    f"""
                    <div style='background-color:{color};padding:12px;border-radius:12px;margin-bottom:6px;
                    box-shadow: 2px 2px 8px rgba(0,0,0,0.1);'>
                        <b>#{i} {row.Name}{crown}</b><br>
                        Score: {row.Score} / {row.Total} &nbsp; | &nbsp; Percentage: {row.Percentage}%
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.subheader("📊 Top Players - Final Visual Ranking")
        show_leaderboard_chart(top5)

        # Show player's rank
        rank_df = leaderboard.reset_index()
        player_rank = rank_df.index[rank_df['Name']==st.session_state.player_name][0] + 1

        # Personalized congratulations
        if player_rank == 1:
            st.success(f"🏆 Amazing {st.session_state.player_name}! You are the top scorer! 👑")
            st.balloons()
            st.audio("winner.mp3", format="audio/mp3")
        elif player_rank <= 3:
            st.success(f"🎉 Great job {st.session_state.player_name}! You are in the top 3! 🥳")
        else:
            st.info(f"👏 Well done {st.session_state.player_name}! Your final rank: #{player_rank}")

        # Restart Quiz Button
        if st.button("🔄 Play Again"):
            for key in ["shuffled_questions", "current_q", "score", "colors"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.experimental_rerun()

# ---------------------------
# Run the App
# ---------------------------
if __name__ == "__main__":
    run_quiz()
