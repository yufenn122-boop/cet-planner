# planner.py - Week1 计划生成（规则模板 + GPT 润色）

import json
from dataclasses import dataclass
from typing import Optional
from analyzer import StudentProfile, AnalysisResult, SECTION_CN
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


@dataclass
class DayPlan:
    day: int          # 1-7
    vocab: str
    reading: str
    other: str        # 听力 / 写作 / 复习，取决于方向
    other_label: str  # "听力" / "写作" / "复习"


@dataclass
class Week1Plan:
    student_name: str
    exam_type: str
    week_goal: str
    days: list        # list[DayPlan]


# ─── 规则模板库 ──────────────────────────────────────────────

# 单词任务模板
VOCAB_TEMPLATES = {
    "薄弱": [
        "新学四六级核心词 Day{d}（30个），用例句辅助记忆，标注难词",
        "新学四六级核心词 Day{d}（30个），重点记忆昨日标注难词 + 新词",
        "新学四六级核心词 Day{d}（30个），默写昨日词汇，错词重点标注",
        "新学四六级核心词 Day{d}（30个），复习 Day1-Day3 词汇，查漏补缺",
        "新学四六级核心词 Day{d}（30个），重点复习本周高频词",
        "复习单词 Day1-Day5 全部词汇，错词整理成错词本",
        "复习单词本周全部词汇，重点攻克错词，准备下周新词",
    ],
    "已有基础": [
        "复习单词四六级高频词 Day{d}（20个），快速过已掌握词，精记生词",
        "复习单词四六级高频词 Day{d}（20个），重点复习昨日生词",
        "复习单词四六级高频词 Day{d}（20个），默写昨日生词，错词重点标注",
        "复习单词四六级高频词 Day{d}（20个），复习 Day1-Day3 生词",
        "复习单词四六级高频词 Day{d}（20个），重点复习本周高频词",
        "复习单词本周全部生词，整理错词本",
        "复习单词本周全部词汇，重点攻克错词",
    ],
}

# 阅读任务模板（A档：仔细阅读；B档：其他题型）
READING_TEMPLATES_A = [
    "仔细阅读：2024年6月四级真题 阅读理解第1篇，限时15分钟，对答案后精析错题逻辑",
    "仔细阅读：2023年12月四级真题 阅读理解第1篇，限时15分钟，整理错题中的阅读高频词",
    "仔细阅读：2023年6月四级真题 阅读理解第1篇，限时15分钟，对答案后分析出题规律",
    "仔细阅读：2022年12月四级真题 阅读理解第1篇，限时15分钟，精析长难句结构",
    "仔细阅读：2022年6月四级真题 阅读理解第1篇，限时15分钟，对答案后整理错题",
    "仔细阅读：2021年12月四级真题 阅读理解第1篇，限时15分钟，复习本周阅读高频词",
    "复习本周阅读错题，整理错题本，总结本周阅读得分规律",
]

READING_TEMPLATES_B = [
    "选词填空：2024年6月四级真题 选词填空，限时10分钟，对答案后分析词性规律",
    "长篇匹配：2023年12月四级真题 长篇匹配，限时15分钟，对答案后精析定位技巧",
    "翻译：2024年6月四级真题 翻译题，限时15分钟，对照参考译文分析差距",
    "选词填空：2023年6月四级真题 选词填空，限时10分钟，整理高频词性搭配",
    "长篇匹配：2022年12月四级真题 长篇匹配，限时15分钟，练习关键词定位法",
    "翻译：2023年12月四级真题 翻译题，限时15分钟，重点练习长句拆分翻译",
    "复习本周阅读/翻译错题，整理错题本，总结本周得分规律",
]

# 听力任务模板（听力最弱时使用）
LISTENING_WEAK_TEMPLATES = [
    "听力方法课：学习听力做题技巧（预读题目、抓关键词），不做题，只听方法讲解",
    "短新闻入门：VOA Special English 慢速新闻 1 篇，精听跟读，听写关键词",
    "四级听力短对话：2024年6月真题 短对话 1-4 题，精听每道题，对答案后逐句跟读",
    "四级听力短对话：2024年6月真题 短对话 5-8 题，精听每道题，整理听力高频词",
    "四级听力长对话：2024年6月真题 长对话第1段，精听，对答案后分析出题规律",
    "复习本周听力错题，重听错题音频，整理听力高频词",
    "复习本周听力内容，跟读练习，巩固听力高频词",
]

# 写译任务模板（写译最弱时轻量接触）
WRITING_LIGHT_TEMPLATES = [
    "写作入门：阅读2024年6月四级真题作文范文，分析段落结构和高分句型，不写作",
    "翻译入门：阅读2024年6月四级真题翻译参考译文，分析长句拆分方法，不翻译",
    "写作练习：抄写2023年12月四级真题作文范文，标注高分句型",
    "翻译练习：翻译2023年12月四级真题翻译题前3句，对照参考译文分析差距",
    "写作练习：背诵2023年6月四级真题作文开头段和结尾段",
    "复习本周写作/翻译笔记，整理高分句型",
    "复习本周写作/翻译内容，巩固高分句型",
]

# 通用复习任务（无明显弱项时）
REVIEW_TEMPLATES = [
    "复习今日单词和阅读错题，整理笔记",
    "复习今日单词，回顾阅读高频词",
    "复习今日单词和阅读错题，标注难点",
    "复习本周 Day1-Day3 内容，查漏补缺",
    "复习今日单词，整理本周阅读高频词",
    "复习本周全部错题，整理错题本",
    "复习本周全部内容，总结学习规律，准备下周计划",
]


def _pick(templates: list, day_index: int) -> str:
    """按天数循环取模板"""
    return templates[day_index % len(templates)]


def _format_vocab(template: str, day: int) -> str:
    return template.format(d=day)


# ─── 规则生成 Week1 ──────────────────────────────────────────

def _build_week1_rules(profile: StudentProfile, analysis: AnalysisResult) -> Week1Plan:
    """纯规则生成 Week1 计划"""
    vocab_key = "薄弱" if not profile.core_vocab_done else "已有基础"
    vocab_templates = VOCAB_TEMPLATES[vocab_key]

    # 阅读档位：接近过线型+阅读强 用A档，其余用B档
    use_reading_a = (
        analysis.stage in ("接近过线型", "冲线准备型", "基础薄弱型")
        or analysis.strong_section == "reading"
    )
    reading_templates = READING_TEMPLATES_A if use_reading_a else READING_TEMPLATES_B

    # 第三部分：听力弱→听力模板；写译弱→写译轻量；其余→复习
    if analysis.weak_section == "listening":
        other_templates = LISTENING_WEAK_TEMPLATES
        other_label = "听力"
    elif analysis.weak_section == "writing_translation":
        other_templates = WRITING_LIGHT_TEMPLATES
        other_label = "写作"
    else:
        other_templates = REVIEW_TEMPLATES
        other_label = "复习"

    days = []
    for i in range(7):
        day_num = i + 1
        days.append(DayPlan(
            day=day_num,
            vocab=_format_vocab(_pick(vocab_templates, i), day_num),
            reading=_pick(reading_templates, i),
            other=_pick(other_templates, i),
            other_label=other_label,
        ))

    # 周目标
    stage = analysis.stage
    weak_cn = SECTION_CN.get(analysis.weak_section, "") if analysis.weak_section else ""
    strong_cn = SECTION_CN.get(analysis.strong_section, "") if analysis.strong_section else ""

    if stage == "基础薄弱型":
        goal = f"建立每日学习习惯，夯实词汇基础，阅读入门，每天完成三部分任务"
    elif stage == "冲线准备型":
        goal = f"稳定每日学习节奏，词汇持续积累，{'重点突破' + weak_cn if weak_cn else '均衡推进'}，向425分冲刺"
    elif stage == "接近过线型":
        goal = f"补词汇基础，{'稳住' + strong_cn if strong_cn else '稳住阅读'}，{'弱项' + weak_cn + '起步' if weak_cn else '弱项起步'}，本周不上整套"
    elif stage == "已过线提升型":
        goal = f"巩固已有优势，{'强化' + weak_cn if weak_cn else '均衡提升'}，向更高分冲刺"
    elif stage == "提优型":
        goal = f"精细化提升，{'重点攻克' + weak_cn if weak_cn else '全面提升'}，冲击高分"
    else:
        goal = f"建立学习节奏，词汇+阅读双线并进，本周以分部分练习为主"

    return Week1Plan(
        student_name=profile.name,
        exam_type=profile.exam_type,
        week_goal=goal,
        days=days,
    )


# ─── GPT 润色 ────────────────────────────────────────────────

def _build_gpt_prompt(profile: StudentProfile, analysis: AnalysisResult, rule_plan: Week1Plan) -> str:
    sections_info = ""
    if profile.last_total_score:
        sections_info = f"""
- 上次总分：{profile.last_total_score}
- 听力：{profile.last_listening}，阅读：{profile.last_reading}，写译：{profile.last_writing_translation}
- 强项：{SECTION_CN.get(analysis.strong_section, '未知')}，弱项：{SECTION_CN.get(analysis.weak_section, '未知')}
- {'明显偏科' if analysis.is_biased else '各科差距不大'}"""
    else:
        sections_info = "- 无历史成绩"

    days_draft = ""
    for dp in rule_plan.days:
        days_draft += f"""
Day{dp.day}:
  【单词】{dp.vocab}
  【阅读】{dp.reading}
  【{dp.other_label}】{dp.other}"""

    prompt = f"""你是一名专业的英语四六级督学老师，正在为学生制定 Week1 学习计划。

## 学生信息
- 姓名：{profile.name}
- 年级：{profile.grade}
- 考试类型：{profile.exam_type}
- 第几次参加：{profile.attempt_count or '首次'}
- 词汇基础：{analysis.vocab_base}
- 每日可用时间：{profile.daily_study_hours}小时{'（时间不固定，有风险）' if profile.daily_time_uncertain else ''}
- 目标分：{profile.target_score}
- 高考英语：{profile.gaokao_english or '未填写'}
{sections_info}

## 分析结果
- 分数阶段：{analysis.stage}
- 任务轻重：{analysis.task_weight}
- 目标分差：{analysis.score_gap_level}
- Week1 方向：{analysis.week1_focus}

## 规则草稿（请在此基础上润色，不要大改结构）
{days_draft}

## 润色要求
1. 保持每天三部分结构：【单词】【阅读】【{rule_plan.days[0].other_label}】
2. 任务描述要具体，不能写空话
3. 不要写"复盘单词"，统一写"复习单词"
4. 不要写"听力生词/阅读生词"，统一写"听力高频词/阅读高频词"
5. 作文和翻译优先用 2024 年及以前真题
6. 第一周以分部分练习为主，不上整套
7. 仔细阅读第一周只做 1 篇练手
8. 阅读部分只能二选一：A档（1篇仔细阅读+对答案）或 B档（选词填空/长篇匹配/翻译 中任选两个组合）
9. 语气亲切自然，像督学老师写给学生的计划
10. 每天每部分控制在 1-2 句话，不要太长

## 输出格式（严格按此 JSON 格式输出，不要有其他内容）
{{
  "week_goal": "本周目标一句话",
  "days": [
    {{
      "day": 1,
      "vocab": "单词任务描述",
      "reading": "阅读任务描述",
      "other": "{rule_plan.days[0].other_label}任务描述",
      "other_label": "{rule_plan.days[0].other_label}"
    }}
  ]
}}
"""
    return prompt


def _call_gpt(prompt: str) -> Optional[dict]:
    """调用 OpenAI GPT，返回解析后的 dict，失败返回 None"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"[GPT 调用失败] {e}")
        return None


def _apply_gpt_result(rule_plan: Week1Plan, gpt_result: dict) -> Week1Plan:
    """将 GPT 结果合并回 Week1Plan"""
    if "week_goal" in gpt_result:
        rule_plan.week_goal = gpt_result["week_goal"]

    gpt_days = {d["day"]: d for d in gpt_result.get("days", [])}
    for dp in rule_plan.days:
        if dp.day in gpt_days:
            gd = gpt_days[dp.day]
            dp.vocab = gd.get("vocab", dp.vocab)
            dp.reading = gd.get("reading", dp.reading)
            dp.other = gd.get("other", dp.other)
            dp.other_label = gd.get("other_label", dp.other_label)

    return rule_plan


# ─── 主入口 ──────────────────────────────────────────────────

def generate_week1(profile: StudentProfile, analysis: AnalysisResult, use_gpt: bool = True) -> Week1Plan:
    """
    生成 Week1 计划。
    use_gpt=True 且 OPENAI_API_KEY 已配置时，调用 GPT 润色；
    否则降级为纯规则模板。
    """
    rule_plan = _build_week1_rules(profile, analysis)

    if use_gpt and OPENAI_API_KEY:
        prompt = _build_gpt_prompt(profile, analysis, rule_plan)
        gpt_result = _call_gpt(prompt)
        if gpt_result:
            rule_plan = _apply_gpt_result(rule_plan, gpt_result)

    return rule_plan
