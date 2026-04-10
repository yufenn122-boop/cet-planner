# analyzer.py - 解析问卷星数据 + 规则分析

import re
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from config import COLUMN_KEYWORDS


# ─── 数据结构 ────────────────────────────────────────────────

@dataclass
class StudentProfile:
    row_index: int
    name: str
    grade: str
    exam_type: str                        # "四级" / "六级"
    attempt_count: Optional[int]
    last_total_score: Optional[float]
    last_listening: Optional[float]
    last_reading: Optional[float]
    last_writing_translation: Optional[float]
    gaokao_english: Optional[float]
    core_vocab_done: bool
    daily_study_hours: float
    daily_time_uncertain: bool            # 时间不固定风险标记
    target_score: Optional[float]


@dataclass
class AnalysisResult:
    stage: str                            # 分数阶段
    strong_section: Optional[str]         # 强项
    weak_section: Optional[str]           # 弱项
    is_biased: bool                       # 明显偏科
    vocab_base: str                       # "已有基础" / "薄弱"
    task_weight: str                      # "轻量" / "标准" / "标准偏完整"
    score_gap: Optional[float]            # 目标分差
    score_gap_level: str                  # "合理" / "有挑战" / "偏高"
    risks: list                           # 风险标记列表
    week1_focus: str                      # Week1 方向描述


# ─── 列名匹配 ────────────────────────────────────────────────

def _match_columns(df_columns: list) -> dict:
    """将 DataFrame 列名模糊匹配到标准字段名，返回 {标准字段: 原始列名}"""
    result = {}
    for std_field, keywords in COLUMN_KEYWORDS.items():
        for col in df_columns:
            col_str = str(col).strip()
            for kw in keywords:
                if re.search(kw, col_str):
                    result[std_field] = col
                    break
            if std_field in result:
                break
    return result


# ─── 解析工具 ────────────────────────────────────────────────

def _to_float(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        m = re.search(r"[\d.]+", str(val))
        return float(m.group()) if m else None


def _to_int(val) -> Optional[int]:
    f = _to_float(val)
    return int(f) if f is not None else None


def _parse_exam_type(val) -> str:
    s = str(val).strip() if val and not (isinstance(val, float) and pd.isna(val)) else ""
    if "六" in s or "6" in s:
        return "六级"
    return "四级"


def _parse_vocab(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip()
    return any(k in s for k in ["是", "背过", "有", "yes", "Yes", "1", "True"])


def _parse_daily_hours(val) -> tuple[float, bool]:
    """返回 (小时数, 是否不固定)"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 1.0, False
    s = str(val).strip()

    uncertain_keywords = ["随便", "不固定", "看情况", "不一定", "说不准", "随时", "不确定"]
    if any(k in s for k in uncertain_keywords):
        return 1.0, True

    # "1-1.5小时" 取均值
    m = re.search(r"([\d.]+)\s*[-~]\s*([\d.]+)\s*[小时hH]?", s)
    if m:
        avg = (float(m.group(1)) + float(m.group(2))) / 2
        return round(avg, 1), False

    # "1.5小时" / "1h"
    m = re.search(r"([\d.]+)\s*[小时hH]", s)
    if m:
        return float(m.group(1)), False

    # "30分钟" / "30min"
    m = re.search(r"([\d.]+)\s*[分钟mM]", s)
    if m:
        return round(float(m.group(1)) / 60, 1), False

    # 纯数字：<=3 视为小时，否则视为分钟
    m = re.search(r"^[\d.]+$", s)
    if m:
        n = float(m.group())
        return (n, False) if n <= 3 else (round(n / 60, 1), False)

    return 1.0, False


# ─── 解析文件 ────────────────────────────────────────────────

def parse_file(file) -> tuple[list[StudentProfile], dict, list[str]]:
    """
    解析上传的文件，返回 (学员列表, 列名映射, 警告列表)
    file 可以是文件路径字符串或 BytesIO
    """
    filename = getattr(file, "name", str(file))
    if filename.endswith(".csv"):
        try:
            df = pd.read_csv(file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="gbk")
    else:
        df = pd.read_excel(file)

    df = df.dropna(how="all")

    col_map = _match_columns(list(df.columns))
    warnings = []

    # 检查必要字段
    required = ["exam_type", "daily_study_hours", "target_score"]
    for f in required:
        if f not in col_map:
            warnings.append(f"未找到字段：{f}（关键词：{COLUMN_KEYWORDS[f]}）")

    students = []
    for idx, row in df.iterrows():
        def get(std_field, default=None):
            col = col_map.get(std_field)
            if col is None:
                return default
            val = row.get(col, default)
            if isinstance(val, float) and pd.isna(val):
                return default
            return val

        exam_type = _parse_exam_type(get("exam_type", "四级"))
        daily_hours, uncertain = _parse_daily_hours(get("daily_study_hours"))

        # 根据 exam_type 选择对应分支字段
        if exam_type == "四级":
            attempt = _to_int(get("attempt_count_cet4"))
            total = _to_float(get("last_total_score_cet4"))
            listening = _to_float(get("last_listening_cet4"))
            reading = _to_float(get("last_reading_cet4"))
            writing = _to_float(get("last_writing_cet4"))
        else:
            attempt = _to_int(get("attempt_count_cet6"))
            total = _to_float(get("last_total_score_cet6"))
            listening = _to_float(get("last_listening_cet6"))
            reading = _to_float(get("last_reading_cet6"))
            writing = _to_float(get("last_writing_cet6"))

        name_val = get("name", "")
        name = str(name_val).strip() if name_val else f"学员{idx+1}"

        profile = StudentProfile(
            row_index=int(idx),
            name=name,
            grade=str(get("grade", "")).strip(),
            exam_type=exam_type,
            attempt_count=attempt,
            last_total_score=total,
            last_listening=listening,
            last_reading=reading,
            last_writing_translation=writing,
            gaokao_english=_to_float(get("gaokao_english")),
            core_vocab_done=_parse_vocab(get("core_vocab_done")),
            daily_study_hours=daily_hours,
            daily_time_uncertain=uncertain,
            target_score=_to_float(get("target_score")),
        )
        students.append(profile)

    return students, col_map, warnings


# ─── 规则分析 ────────────────────────────────────────────────

def _get_stage(total: Optional[float], exam_type: str) -> str:
    """分数阶段判断（四六级规则相同）"""
    if total is None:
        return "首次参加"
    if total < 350:
        return "基础薄弱型"
    elif total < 390:
        return "冲线准备型"
    elif total < 425:
        return "接近过线型"
    elif total < 480:
        return "已过线提升型"
    else:
        return "提优型"


SECTION_CN = {"listening": "听力", "reading": "阅读", "writing_translation": "写译"}


def _get_strong_weak(listening, reading, writing) -> tuple[Optional[str], Optional[str], bool]:
    """返回 (强项key, 弱项key, 是否明显偏科)"""
    scores = {}
    if listening is not None:
        scores["listening"] = listening
    if reading is not None:
        scores["reading"] = reading
    if writing is not None:
        scores["writing_translation"] = writing

    if len(scores) < 2:
        return None, None, False

    strong = max(scores, key=scores.get)
    weak = min(scores, key=scores.get)
    biased = (scores[strong] - scores[weak]) >= 20
    return strong, weak, biased


def analyze(profile: StudentProfile) -> AnalysisResult:
    stage = _get_stage(profile.last_total_score, profile.exam_type)
    strong, weak, biased = _get_strong_weak(
        profile.last_listening, profile.last_reading, profile.last_writing_translation
    )

    vocab_base = "已有基础" if profile.core_vocab_done else "薄弱"

    # 任务轻重
    h = profile.daily_study_hours
    if profile.daily_time_uncertain:
        task_weight = "标准"
    elif h < 1:
        task_weight = "轻量"
    elif h <= 1.5:
        task_weight = "标准"
    else:
        task_weight = "标准偏完整"

    # 目标分差
    score_gap = None
    score_gap_level = "未知"
    if profile.target_score is not None and profile.last_total_score is not None:
        score_gap = profile.target_score - profile.last_total_score
        if score_gap <= 20:
            score_gap_level = "目标合理"
        elif score_gap <= 50:
            score_gap_level = "有挑战但可接受"
        else:
            score_gap_level = "目标偏高"

    # 风险标记
    risks = []
    if profile.daily_time_uncertain:
        risks.append("复习时间不固定")
    if score_gap is not None and score_gap > 50:
        risks.append("目标分差过大，需调整预期")
    if profile.last_total_score is None and profile.gaokao_english is None:
        risks.append("无历史成绩参考，计划基于默认假设")

    # Week1 方向
    focus_parts = []
    if stage == "接近过线型" and strong == "reading" and not profile.core_vocab_done:
        focus_parts.append("补单词基础、稳阅读、弱项起步")
    elif stage == "基础薄弱型":
        focus_parts.append("夯实词汇、阅读入门、建立学习节奏")
    elif stage in ("已过线提升型", "提优型"):
        focus_parts.append("强化弱项、提升综合分")
    else:
        focus_parts.append("均衡推进、重点突破弱项")

    if weak == "listening":
        focus_parts.append("加入听力方法课/短新闻入门")
    elif weak == "writing_translation":
        focus_parts.append("写译轻量接触，不作主攻")

    if not profile.core_vocab_done:
        focus_parts.append("每日新词30分钟")

    week1_focus = "；".join(focus_parts)

    return AnalysisResult(
        stage=stage,
        strong_section=strong,
        weak_section=weak,
        is_biased=biased,
        vocab_base=vocab_base,
        task_weight=task_weight,
        score_gap=score_gap,
        score_gap_level=score_gap_level,
        risks=risks,
        week1_focus=week1_focus,
    )
