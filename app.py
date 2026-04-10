# app.py - Streamlit 主程序

import streamlit as st
import pandas as pd
from analyzer import parse_file, analyze, SECTION_CN
from planner import generate_week1
from exporter import export_to_excel
import config as _cfg

# Streamlit Cloud 上从 st.secrets 读取，本地从 config.py 读取
try:
    _cfg.OPENAI_API_KEY  = st.secrets.get("OPENAI_API_KEY",  _cfg.OPENAI_API_KEY)
    _cfg.OPENAI_BASE_URL = st.secrets.get("OPENAI_BASE_URL", _cfg.OPENAI_BASE_URL)
    _cfg.OPENAI_MODEL    = st.secrets.get("OPENAI_MODEL",    _cfg.OPENAI_MODEL)
except Exception:
    pass

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

st.set_page_config(
    page_title="四六级督学 Week1 计划生成器",
    page_icon="📚",
    layout="wide",
)

st.title("📚 四六级督学 Week1 计划生成器")
st.caption("上传问卷星导出的 Excel/CSV → 自动分析学员情况 → 生成 Week1 学习计划 → 导出 Excel")

# ─── 侧边栏：配置 ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 配置")

    api_key_input = st.text_input(
        "OpenAI API Key",
        value=OPENAI_API_KEY,
        type="password",
        help="填入后使用 GPT 润色计划内容；留空则使用纯规则模板",
    )
    use_gpt = bool(api_key_input)
    if use_gpt:
        st.success("已配置 API Key，将使用 GPT 润色")
    else:
        st.info("未配置 API Key，使用纯规则模板生成")

    st.divider()
    st.markdown("**列名匹配说明**")
    st.markdown(
        "程序会自动识别问卷星导出的中文列名。\n\n"
        "如果解析结果有误，请检查下方「列名映射」是否正确。"
    )

# ─── 主区域 ──────────────────────────────────────────────────

# Step 1: 上传文件
st.subheader("① 上传问卷文件")
uploaded = st.file_uploader(
    "支持 .xlsx / .xls / .csv",
    type=["xlsx", "xls", "csv"],
    help="请上传问卷星导出的原始文件，不需要提前处理",
)

if uploaded is None:
    st.info("请上传文件以开始")
    st.stop()

# ─── 解析文件 ────────────────────────────────────────────────
with st.spinner("正在解析文件..."):
    try:
        students, col_map, warnings = parse_file(uploaded)
    except Exception as e:
        st.error(f"文件解析失败：{e}")
        st.stop()

if warnings:
    with st.expander("⚠️ 解析警告（部分字段未找到）", expanded=True):
        for w in warnings:
            st.warning(w)

if not students:
    st.error("未解析到有效学员数据，请检查文件格式")
    st.stop()

# Step 2: 显示列名映射
with st.expander("🔍 列名映射（点击展开确认）", expanded=False):
    map_rows = [{"标准字段": k, "匹配到的列名": v} for k, v in col_map.items()]
    st.dataframe(pd.DataFrame(map_rows), use_container_width=True, hide_index=True)

# Step 3: 显示解析后的学员信息
st.subheader(f"② 解析结果（共 {len(students)} 名学员）")

student_rows = []
for p in students:
    student_rows.append({
        "姓名": p.name,
        "年级": p.grade,
        "考试类型": p.exam_type,
        "第几次": p.attempt_count or "首次",
        "上次总分": p.last_total_score or "-",
        "听力": p.last_listening or "-",
        "阅读": p.last_reading or "-",
        "写译": p.last_writing_translation or "-",
        "高考英语": p.gaokao_english or "-",
        "核心词": "已背" if p.core_vocab_done else "未背",
        "每日时间(h)": p.daily_study_hours,
        "时间不固定": "⚠️" if p.daily_time_uncertain else "",
        "目标分": p.target_score or "-",
    })

st.dataframe(pd.DataFrame(student_rows), use_container_width=True, hide_index=True)

# Step 4: 显示分析结果
st.subheader("③ 规则分析结果")

analyses = [analyze(p) for p in students]

analysis_rows = []
for p, a in zip(students, analyses):
    strong_cn = SECTION_CN.get(a.strong_section, "-") if a.strong_section else "-"
    weak_cn = SECTION_CN.get(a.weak_section, "-") if a.weak_section else "-"
    analysis_rows.append({
        "姓名": p.name,
        "分数阶段": a.stage,
        "强项": strong_cn,
        "弱项": weak_cn,
        "偏科": "是" if a.is_biased else "否",
        "词汇基础": a.vocab_base,
        "任务轻重": a.task_weight,
        "目标分差": f"{a.score_gap:+.0f}" if a.score_gap is not None else "-",
        "分差评估": a.score_gap_level,
        "风险": "；".join(a.risks) if a.risks else "无",
        "Week1方向": a.week1_focus,
    })

st.dataframe(pd.DataFrame(analysis_rows), use_container_width=True, hide_index=True)

# Step 5: 生成计划
st.subheader("④ 生成 Week1 计划")

if use_gpt:
    st.info(f"将使用 GPT（{st.session_state.get('model', 'gpt-4o-mini')}）润色计划内容，每位学员约需 5-15 秒")
else:
    st.info("使用纯规则模板生成，速度较快")

if st.button("🚀 生成 Week1 计划", type="primary", use_container_width=True):
    plans = []
    progress = st.progress(0, text="准备生成...")
    status_area = st.empty()

    # 如果用 GPT，临时覆盖 config 中的 API Key
    if use_gpt and api_key_input:
        import config as _cfg
        _cfg.OPENAI_API_KEY = api_key_input

    for i, (profile, analysis) in enumerate(zip(students, analyses)):
        status_area.info(f"正在生成：{profile.name}（{i+1}/{len(students)}）")
        try:
            plan = generate_week1(profile, analysis, use_gpt=use_gpt)
            plans.append(plan)
        except Exception as e:
            st.warning(f"⚠️ {profile.name} 生成失败：{e}，已跳过")
        progress.progress((i + 1) / len(students), text=f"已完成 {i+1}/{len(students)}")

    status_area.empty()
    progress.empty()

    if not plans:
        st.error("所有学员生成失败，请检查配置")
        st.stop()

    st.success(f"✅ 成功生成 {len(plans)} 份 Week1 计划")
    st.session_state["plans"] = plans

# Step 6: 预览 + 下载
if "plans" in st.session_state and st.session_state["plans"]:
    plans = st.session_state["plans"]

    st.subheader("⑤ 预览计划内容")

    selected_name = st.selectbox(
        "选择学员预览",
        options=[p.student_name for p in plans],
    )
    selected_plan = next(p for p in plans if p.student_name == selected_name)

    st.markdown(f"**本周目标：** {selected_plan.week_goal}")
    st.divider()

    cols = st.columns(7)
    for i, (col, dp) in enumerate(zip(cols, selected_plan.days)):
        with col:
            st.markdown(f"**Day{dp.day}**")
            st.markdown(f"**【单词】**\n\n{dp.vocab}")
            st.markdown("---")
            st.markdown(f"**【阅读】**\n\n{dp.reading}")
            st.markdown("---")
            st.markdown(f"**【{dp.other_label}】**\n\n{dp.other}")

    st.divider()
    st.subheader("⑥ 导出 Excel")

    with st.spinner("正在生成 Excel..."):
        excel_buf = export_to_excel(plans)

    st.download_button(
        label="⬇️ 下载 Week1 计划 Excel",
        data=excel_buf,
        file_name="Week1_学习计划.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
