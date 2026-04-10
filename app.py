# app.py - Streamlit 主程序（移动端适配版）

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
    page_title="四六级督学计划生成器",
    page_icon="📚",
    layout="centered",
)

# ─── 密码验证 ─────────────────────────────────────────────────
def _check_password():
    correct = st.secrets.get("APP_PASSWORD", "") if hasattr(st, "secrets") else ""
    if not correct:
        return  # 本地未配置密码时直接放行

    if st.session_state.get("authenticated"):
        return

    st.markdown("## 🔒 请输入访问密码")
    pwd = st.text_input("密码", type="password", key="pwd_input")
    if st.button("进入", use_container_width=True):
        if pwd == correct:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("密码错误，请重试")
    st.stop()

_check_password()

# ─── 全局移动端 CSS ───────────────────────────────────────────
st.markdown("""
<style>
/* 整体字体和间距 */
html, body, [class*="css"] {
    font-size: 15px;
}

/* 标题缩小 */
h1 { font-size: 1.4rem !important; }
h2 { font-size: 1.15rem !important; }
h3 { font-size: 1.05rem !important; }

/* 按钮加大点击区域 */
.stButton > button {
    min-height: 48px;
    font-size: 1rem;
    border-radius: 8px;
}

/* 下载按钮 */
.stDownloadButton > button {
    min-height: 48px;
    font-size: 1rem;
    border-radius: 8px;
}

/* 计划卡片 */
.plan-card {
    background: #f0f6ff;
    border-left: 4px solid #1F4E79;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 12px;
}
.plan-card .day-title {
    font-weight: bold;
    font-size: 1rem;
    color: #1F4E79;
    margin-bottom: 6px;
}
.plan-card .task-block {
    margin-bottom: 6px;
    line-height: 1.5;
}
.plan-card .task-label {
    font-weight: bold;
    color: #333;
}

/* 学员信息卡片 */
.student-card {
    background: #fff;
    border: 1px solid #dde6f0;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
}
.student-card .s-name {
    font-size: 1.05rem;
    font-weight: bold;
    color: #1F4E79;
    margin-bottom: 4px;
}
.student-card .s-row {
    font-size: 0.88rem;
    color: #555;
    margin-bottom: 2px;
}

/* 分析结果卡片 */
.analysis-card {
    background: #f8fdf4;
    border: 1px solid #c6e0b4;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
}
.analysis-card .a-name {
    font-size: 1rem;
    font-weight: bold;
    color: #375623;
    margin-bottom: 4px;
}
.analysis-card .a-row {
    font-size: 0.88rem;
    color: #444;
    margin-bottom: 2px;
}
.tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: bold;
    margin-right: 4px;
}
.tag-blue  { background: #dbeafe; color: #1e40af; }
.tag-green { background: #dcfce7; color: #166534; }
.tag-red   { background: #fee2e2; color: #991b1b; }
.tag-yellow{ background: #fef9c3; color: #854d0e; }
</style>
""", unsafe_allow_html=True)

st.title("📚 四六级督学计划生成器")
st.caption("上传问卷星 Excel/CSV → 分析学员 → 生成 Week1 计划 → 导出")

# ─── API Key 配置（可折叠，默认收起）────────────────────────
with st.expander("⚙️ GPT 配置（可选）", expanded=False):
    api_key_input = st.text_input(
        "OpenAI API Key",
        value=OPENAI_API_KEY,
        type="password",
        help="填入后使用 GPT 润色计划内容；留空则使用纯规则模板",
    )
    if api_key_input:
        st.success("已配置 API Key，将使用 GPT 润色")
    else:
        st.info("未配置 API Key，使用纯规则模板生成")

use_gpt = bool(api_key_input)

# ─── Step 1: 上传文件 ─────────────────────────────────────────
st.subheader("① 上传问卷文件")
uploaded = st.file_uploader(
    "支持 .xlsx / .xls / .csv",
    type=["xlsx", "xls", "csv"],
    help="请上传问卷星导出的原始文件",
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

# ─── 列名映射（折叠） ─────────────────────────────────────────
with st.expander("🔍 列名映射（点击展开确认）", expanded=False):
    map_rows = [{"标准字段": k, "匹配到的列名": v} for k, v in col_map.items()]
    st.dataframe(pd.DataFrame(map_rows), use_container_width=True, hide_index=True)

# ─── Step 2: 学员信息（卡片式，移动端友好）──────────────────
st.subheader(f"② 解析结果（共 {len(students)} 名学员）")

for p in students:
    score_str = f"{p.last_total_score:.0f}" if p.last_total_score else "无"
    sub_str = ""
    if p.last_listening or p.last_reading or p.last_writing_translation:
        parts = []
        if p.last_listening:       parts.append(f"听{p.last_listening:.0f}")
        if p.last_reading:         parts.append(f"读{p.last_reading:.0f}")
        if p.last_writing_translation: parts.append(f"写译{p.last_writing_translation:.0f}")
        sub_str = " / ".join(parts)

    st.markdown(f"""
<div class="student-card">
  <div class="s-name">{p.name}</div>
  <div class="s-row">🎯 {p.exam_type} &nbsp;|&nbsp; 目标 {p.target_score or '-'} 分 &nbsp;|&nbsp; 每日 {p.daily_study_hours}h{'⚠️' if p.daily_time_uncertain else ''}</div>
  <div class="s-row">📊 上次总分：{score_str}{('（' + sub_str + '）') if sub_str else ''}</div>
  <div class="s-row">📖 核心词：{'已背' if p.core_vocab_done else '未背'} &nbsp;|&nbsp; 年级：{p.grade or '-'} &nbsp;|&nbsp; 第 {p.attempt_count or '首'} 次</div>
</div>
""", unsafe_allow_html=True)

# ─── Step 3: 分析结果（卡片式）──────────────────────────────
st.subheader("③ 规则分析结果")

analyses = [analyze(p) for p in students]

for p, a in zip(students, analyses):
    strong_cn = SECTION_CN.get(a.strong_section, "-") if a.strong_section else "-"
    weak_cn   = SECTION_CN.get(a.weak_section,   "-") if a.weak_section   else "-"
    gap_str   = f"{a.score_gap:+.0f}" if a.score_gap is not None else "-"
    risk_str  = "；".join(a.risks) if a.risks else "无"

    # 分差标签颜色
    if a.score_gap_level == "目标合理":
        gap_tag = f'<span class="tag tag-green">{a.score_gap_level}</span>'
    elif a.score_gap_level == "有挑战但可接受":
        gap_tag = f'<span class="tag tag-yellow">{a.score_gap_level}</span>'
    elif a.score_gap_level == "目标偏高":
        gap_tag = f'<span class="tag tag-red">{a.score_gap_level}</span>'
    else:
        gap_tag = f'<span class="tag tag-blue">{a.score_gap_level}</span>'

    bias_tag = '<span class="tag tag-red">偏科</span>' if a.is_biased else ""

    st.markdown(f"""
<div class="analysis-card">
  <div class="a-name">{p.name} &nbsp; <span class="tag tag-blue">{a.stage}</span> {bias_tag}</div>
  <div class="a-row">💪 强项：{strong_cn} &nbsp;|&nbsp; ⚠️ 弱项：{weak_cn}</div>
  <div class="a-row">📚 词汇：{a.vocab_base} &nbsp;|&nbsp; 任务量：{a.task_weight}</div>
  <div class="a-row">🎯 分差：{gap_str} &nbsp; {gap_tag}</div>
  <div class="a-row">🗓 Week1 方向：{a.week1_focus}</div>
  {'<div class="a-row">🚨 风险：' + risk_str + '</div>' if a.risks else ''}
</div>
""", unsafe_allow_html=True)

# ─── Step 4: 生成计划 ─────────────────────────────────────────
st.subheader("④ 生成 Week1 计划")

if use_gpt:
    st.info(f"将使用 GPT 润色计划内容，每位学员约需 5-15 秒")
else:
    st.info("使用纯规则模板生成")

if st.button("🚀 生成 Week1 计划", type="primary", use_container_width=True):
    plans = []
    progress = st.progress(0, text="准备生成...")
    status_area = st.empty()

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

# ─── Step 5: 预览（卡片式，垂直滚动）────────────────────────
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

    # 垂直卡片，每天一张，手机上顺畅滚动
    for dp in selected_plan.days:
        st.markdown(f"""
<div class="plan-card">
  <div class="day-title">Day {dp.day}</div>
  <div class="task-block"><span class="task-label">【单词】</span><br>{dp.vocab}</div>
  <div class="task-block"><span class="task-label">【阅读】</span><br>{dp.reading}</div>
  <div class="task-block"><span class="task-label">【{dp.other_label}】</span><br>{dp.other}</div>
</div>
""", unsafe_allow_html=True)

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
