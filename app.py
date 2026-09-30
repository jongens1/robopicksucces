import json
import re
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Analýza Úspešnosti Robotov", page_icon="🤖", layout="wide"
)


@st.cache_data
def parse_log_data(file_content):
    """Spracuje surový logový text na Pandas DataFrame."""
    rows = []
    lines = file_content.decode("utf-8").splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Presná extrakcia Robot ID (iba prvé čísla na začiatku riadku, napr. 570)
        robot_match = re.match(r"^(\d+)", line)
        if not robot_match:
            continue
        robot_id = robot_match.group(1)

        # Extrakcia ProductCode
        prod_match = re.search(r"@ProductCode=([^;]+)", line)
        product_code = prod_match.group(1) if prod_match else "UNKNOWN"

        # Extrakcia JSONu z @PropertiesJsonText
        json_match = re.search(r"@PropertiesJsonText=(\{.*?\})$", line)
        json_data = {}

        if json_match:
            try:
                json_data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Parsovanie Sereact výsledkov
        is_robo_picked = (
            str(json_data.get("robo:sereact:IsRoboPicked", ""))
            .strip()
            .lower()
            == "true"
        )
        is_success = (
            str(json_data.get("robo:sereact:IsRoboPickedSuccess", ""))
            .strip()
            .lower()
            == "true"
        )
        error_code = json_data.get("robo:sereact:RoboPickErrorCode", None)

        rows.append(
            {
                "RobotID": f"Robot {robot_id}",
                "ProductCode": product_code,
                "IsRoboPicked": is_robo_picked,
                "IsRoboPickedSuccess": is_success,
                "RoboPickErrorCode": error_code
                if error_code
                else ("OK" if is_success else "UNKNOWN"),
            }
        )

    return pd.DataFrame(rows)


# Title & Header
st.title("🤖 Dashboard Úspešnosti Robotického Pickovania")

# Sidebar Upload & Filter
uploaded_file = st.sidebar.file_uploader(
    "Vložte logovací súbor (.txt / .log)", type=["txt", "log"]
)

if uploaded_file is not None:
    df = parse_log_data(uploaded_file.getvalue())

    available_robots = sorted(df["RobotID"].unique().tolist())
    selected_robots = st.sidebar.multiselect(
        "Vyber robotov:", available_robots, default=available_robots
    )

    filtered_df = df[df["RobotID"].isin(selected_robots)]

    # Top KPI Metriky
    total_picks = len(filtered_df)
    successful_picks = filtered_df["IsRoboPickedSuccess"].sum()
    failed_picks = total_picks - successful_picks
    success_rate = (
        (successful_picks / total_picks * 100) if total_picks > 0 else 0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Celkový počet pokusov", f"{total_picks:,}")
    col2.metric("Úspešné picky", f"{successful_picks:,}")
    col3.metric("Neúspešné picky", f"{failed_picks:,}")
    col4.metric("Celková úspešnosť", f"{success_rate:.2f}%")

    st.markdown("---")

    # Sekcia: Graf Úspešnosti podľa Robotov (5 riadkov)
    st.subheader("📊 Úspešnosť podľa robotov")

    robot_stats = (
        filtered_df.groupby("RobotID")
        .agg(
            Total=("IsRoboPickedSuccess", "count"),
            Success=("IsRoboPickedSuccess", "sum"),
        )
        .reset_index()
    )

    robot_stats["SuccessRate"] = (
        robot_stats["Success"] / robot_stats["Total"] * 100
    ).round(2)
    robot_stats["LabelText"] = robot_stats.apply(
        lambda r: f"{r['SuccessRate']:.2f}% ({r['Success']}/{r['Total']})",
        axis=1,
    )

    # Zotriedenie pre prehľadné zobrazenie v grafe
    robot_stats = robot_stats.sort_values(by="RobotID", ascending=True)

    # Horizontálny stĺpcový graf (každý robot má vlastný riadok)
    fig_robots = px.bar(
        robot_stats,
        x="SuccessRate",
        y="RobotID",
        orientation="h",
        text="LabelText",
        labels={"RobotID": "Robot", "SuccessRate": "Úspešnosť (%)"},
        color="SuccessRate",
        color_continuous_scale="RdYlGn",
        range_color=[70, 100],
    )

    fig_robots.update_traces(
        textposition="inside", insidetextanchor="end", textfont_size=14
    )
    fig_robots.update_layout(
        xaxis_range=[0, 105], yaxis=dict(autorange="reversed"), height=350
    )

    st.plotly_chart(fig_robots, use_container_width=True)

    # Sekcia: Analýza Chýb a Top 10 produktov
    st.markdown("---")
    st.subheader("⚠️ Analýza Chýb a Zlyhaní")

    failed_df = filtered_df[filtered_df["IsRoboPickedSuccess"] == False]

    if len(failed_df) > 0:
        err_col1, err_col2 = st.columns(2)

        with err_col1:
            error_counts = (
                failed_df["RoboPickErrorCode"].value_counts().reset_index()
            )
            error_counts.columns = ["ErrorCode", "Count"]

            fig_pie = px.pie(
                error_counts,
                names="ErrorCode",
                values="Count",
                title="Rozdelenie chybových kódov (Error Codes)",
                hole=0.4,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with err_col2:
            st.write("### Top 10 produktov s neúspešným pickom")
            top_failed_products = (
                failed_df["ProductCode"].value_counts().head(10).reset_index()
            )
            top_failed_products.columns = [
                "Kód produktu",
                "Počet zlyhaní",
            ]
            st.dataframe(
                top_failed_products, use_container_width=True, hide_index=True
            )
    else:
        st.success("V vybraných dátach sa nenachádzajú žiadne zlyhané picky!")

else:
    st.info("👆 Prosím, nahrajte súbor s logmi v ľavom menu.")
