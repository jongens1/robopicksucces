import json
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

        # Získanie Robot ID (prvý kľúč pred medzerou)
        parts = line.split(" ", 1)
        robot_id = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        # Extrakcia JSONu z @PropertiesJsonText
        json_match = re.search(r"@PropertiesJsonText=(\{.*?\})$", rest)
        json_data = {}

        if json_match:
            json_str = json_match.group(1)
            try:
                json_data = json.loads(json_str)
            except json.JSONDecodeError:
                pass
            # Odstránime JSON časť z riadku pre ľahšie spracovanie zvyšných parametrov
            rest = rest[: json_match.start()]

        # Extrakcia parametrov typu @Key=Value
        kv_pairs = re.findall(r"@(\w+)=([^;]*)", rest)
        row_dict = {"RobotID": robot_id}
        for k, v in kv_pairs:
            row_dict[k] = v

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

        row_dict["IsRoboPicked"] = is_robo_picked
        row_dict["IsRoboPickedSuccess"] = is_success
        row_dict["RoboPickErrorCode"] = (
            error_code if error_code else ("OK" if is_success else "UNKNOWN")
        )

        rows.append(row_dict)

    df = pd.DataFrame(rows)
    return df


# Title & Header
st.title("🤖 Dashboard Úspešnosti Robotického Pickovania")
st.markdown(
    "Uploadnite logovací súbor pre analýzu úspešnosti pickovania podľa jednotlivých robotov a chybovosti."
)

# Upload súboru
uploaded_file = st.sidebar.file_uploader(
    "Vložte logovací súbor (.txt / .log)", type=["txt", "log"]
)

if uploaded_file is not None:
    df = parse_log_data(uploaded_file.getvalue())

    # Sidebar Filter
    st.sidebar.header("Filtre")
    available_robots = sorted(df["RobotID"].unique().tolist())
    selected_robots = st.sidebar.multiselect(
        "Vyber robotov:", available_robots, default=available_robots
    )

    filtered_df = df[df["RobotID"].isin(selected_robots)]

    # Top KPIs
    total_picks = len(filtered_df)
    successful_picks = filtered_df["IsRoboPickedSuccess"].sum()
    failed_picks = total_picks - successful_picks
    success_rate = (
        (successful_picks / total_picks * 100) if total_picks > 0 else 0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Celkový počet pokusov", f"{total_picks:,}")
    col2.metric(
        "Úspešné picky", f"{successful_picks:,}", delta=f"{success_rate:.2f}%"
    )
    col3.metric("Neúspešné picky", f"{failed_picks:,}")
    col4.metric(
        "Celková úspešnosť",
        f"{success_rate:.1f}%",
        delta_color="normal" if success_rate > 90 else "inverse",
    )

    st.markdown("---")

    # Sekcia: Prehľad podľa Robotov
    st.subheader("📊 Úspešnosť podľa robotov")

    # Agregácia dát podľa robota
    robot_stats = (
        filtered_df.groupby("RobotID")
        .agg(
            Total=("IsRoboPickedSuccess", "count"),
            Success=("IsRoboPickedSuccess", "sum"),
        )
        .reset_index()
    )

    robot_stats["Failed"] = robot_stats["Total"] - robot_stats["Success"]
    robot_stats["SuccessRate"] = (
        robot_stats["Success"] / robot_stats["Total"] * 100
    ).round(2)

    chart_col, table_col = st.columns([3, 2])

    with chart_col:
        # Graf úspešnosti per robot
        fig = px.bar(
            robot_stats,
            x="RobotID",
            y="SuccessRate",
            text="SuccessRate",
            labels={
                "RobotID": "Robot",
                "SuccessRate": "Úspešnosť (%)",
            },
            title="Úspešnosť jednotlivých robotov (%)",
            color="SuccessRate",
            color_continuous_scale="RdYlGn",
            range_color=[70, 100],
        )
        fig.update_traces(
            texttemplate="%{text:.1f}%", textposition="outside"
        )
        fig.update_layout(yaxis_range=[0, 110])
        st.plotly_chart(fig, use_container_width=True)

    with table_col:
        st.write("### Detailná tabuľka")
        st.dataframe(
            robot_stats.sort_values(by="SuccessRate", ascending=False),
            column_config={
                "RobotID": "Robot",
                "Total": "Pokusy",
                "Success": "Úspešné",
                "Failed": "Zlyhané",
                "SuccessRate": st.column_config.NumberColumn(
                    "Úspešnosť", format="%.2f %%"
                ),
            },
            hide_index=True,
            use_container_width=True,
        )

    # Sekcia: Analýza Chýb (Failures)
    st.markdown("---")
    st.subheader("⚠️ Analýza Chýb a Zlyhaní")

    failed_df = filtered_df[filtered_df["IsRoboPickedSuccess"] == False]

    if len(failed_df) > 0:
        err_col1, err_col2 = st.columns(2)

        with err_col1:
            # Dôvody zlyhania
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
            # Najčastejšie chybové produkty
            st.write("### Top 10 produktov s neúspešným pickom")
            top_failed_products = (
                failed_df["ProductCode"].value_counts().head(10).reset_index()
            )
            top_failed_products.columns = [
                "Kód produktu",
                "Počet zlyhaní",
            ]
            st.dataframe(top_failed_products, use_container_width=True)

    else:
        st.success("V vybraných dátach sa nenachádzajú žiadne zlyhané picky!")

    # Sekcia: Surové dáta
    with st.expander("🔍 Zobraziť prehliadač dát (Raw Data)"):
        st.dataframe(filtered_df)

else:
    st.info("👆 Prosím, nahrajte súbor s logmi pomocou ľavého menu.")
