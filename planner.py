# planner.py - Week1 计划生成（规则模板 + GPT 润色）

import json
from dataclasses import dataclass
from typing import Optional
from analyzer import StudentProfile, AnalysisResult, SECTION_CN
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


@dataclass
class DayPlan:
    day: int
    vocab: str
    reading: str
    other: str
    other_label: str


@dataclass
class Week1Plan:
    student_name: str
    exam_type: str
    week_goal: str
    days: list  # list[DayPlan]


# ─── 规则模板库（按天递进，不再循环取） ──────────────────────

# 单词：未背过核心词（每天新背+复习+补充高频词）
VOCAB_NEW = [
    "背四级核心高频词30个，用例句辅助记忆；补充阅读高频词10个\n要求：把30个里最不熟的10个单独记下来",
    "复习Day1的30个核心词；新背核心词20个；补充听力高频词10个\n要求：把今天仍记不住的词单独标出来",
    "复习前两天核心词50个；补充翻译高频词10个\n要求：把重复看过仍不熟的10个词再过一遍",
    "复习已背核心词50个；新背核心词20个；补充听力高频词10个\n要求：把不熟的词抄一遍",
    "复习本周已背核心词；补充写作高频词10个\n要求：把不熟的词抄一遍",
    "复习本周已背核心词；重点过之前抄过不熟的词；补充听力高频词10个",
    "复习本周已背核心词；重点过之前抄过不熟的词",
]

# 单词：已背过核心词（巩固复习为主）
VOCAB_REVIEW = [
    "复习四六级核心高频词40个，快速过已掌握词，精记生词；补充阅读高频词10个\n要求：把仍不熟的词单独标出来",
    "复习昨日生词；新过核心词30个；补充听力高频词10个\n要求：把今天仍记不住的词单独标出来",
    "默写昨日生词，错词重点标注；补充翻译高频词10个",
    "复习本周已过核心词；新过核心词30个；补充听力高频词10个\n要求：把不熟的词抄一遍",
    "复习本周全部生词；补充写作高频词10个\n要求：把不熟的词抄一遍",
    "重点过本周抄过不熟的词；补充听力高频词10个",
    "复习本周全部词汇；重点攻克错词",
]

# 阅读（7天递进：Day1仔细阅读入门→Day3选词填空→Day5长篇匹配→Day6写作轻触→Day7复盘）
READING_7 = [
    "1篇仔细阅读（2024及以前真题）\n先限时完成，再对答案\n记录：对了几题 / 错了几题 / 最影响理解的5个词",
    "1篇仔细阅读（2023年真题）\n限时完成，对答案，把错题对应到原文句子\n打卡要交：正确题数",
    "选词填空1篇（限时10分钟）\n对答案后分析词性规律，整理3个高频词性搭配",
    "1篇仔细阅读（2022年真题）\n限时完成，对答案，记录正确率和Day1对比\n打卡要交：正确题数",
    "长篇匹配1篇（限时15分钟）\n练习关键词定位法，对答案后标出每题定位词",
    "选词填空1篇 + 长篇匹配1篇\n选词填空限时10分钟，长篇匹配限时15分钟",
    "复习本周阅读错题\n总结：①本周阅读正确率波动 ②最常错的2类题型",
]

# 听力弱（7天递进：方法课→短新闻入门→练习→强化→复盘）
LISTENING_WEAK_7 = [
    "看烤鸭TV第1集《四级听力备考全攻略》\n边看边记笔记，整理出3条做题思路",
    "看烤鸭TV第2集《贯穿四级听力的核心概念》\n边看边记笔记，最后整理出3条你今天记住的做题思路",
    "看烤鸭TV第3集《短篇新闻 题型详解》\n重点记：短新闻常见设问方式、关键词位置、听前该看什么",
    "短新闻1组\n做题前先看题干关键词；做完后对答案\n整理3个没听清的点 + 3个听力高频词\n打卡要交：正确题数",
    "短新闻1组\n要求：做题 + 对答案 + 回听原文，把每题对应的定位词标出来\n打卡要交：正确题数",
    "短新闻1组\n总结错因：是没听到关键词、定位慢、还是选项理解错？",
    "回顾烤鸭TV第2、3集笔记；把本周做过的短新闻里错得最多的1组重听一遍\n与第一次做对比，总结仍听不出来的原因",
]

# 写译弱（7天递进：读范文→轻练→写提纲→翻译→复盘）
WRITING_WEAK_7 = [
    "写作入门：阅读2024年6月四级真题作文范文\n分析段落结构和高分句型，不写作\n整理3个可以直接套用的句型",
    "翻译入门：阅读2024年6月四级真题翻译参考译文\n分析长句拆分方法，不翻译\n整理2个翻译技巧",
    "写作轻练：写1篇四级作文提纲 + 开头段\n先列中文思路3点，再写英文开头段\n开头段必须包含：主题句 + 个人态度",
    "翻译练习：翻译1段（2024及以前真题）\n限时20分钟，最后只改3处最明显错误\n重点看：主干是否完整、时态是否乱",
    "写作练习：抄写2023年12月四级真题作文范文\n标注高分句型，背诵开头段和结尾段",
    "翻译练习：翻译1段（2023年真题）\n对照参考译文，分析差距\n打卡要交：翻译完成截图",
    "复习本周写作/翻译笔记\n整理高分句型，总结本周写译最大收获",
]

# 无明显弱项（均衡复习）
REVIEW_7 = [
    "复习今日单词和阅读错题，整理笔记",
    "复习今日单词，回顾阅读高频词，整理错题",
    "翻译练习：翻译1段（2024及以前真题），限时15分钟，对照参考译文分析差距",
    "复习本周 Day1-Day3 内容，查漏补缺",
    "写作轻练：写1篇四级作文开头段，整理本周阅读高频词",
    "复习本周全部错题，整理错题本",
    "复习本周全部内容，总结学习规律，准备下周计划",
]


# ─── 规则生成 Week1 ──────────────────────────────────────────

def _build_week1_rules(profile: StudentProfile, analysis: AnalysisResult) -> Week1Plan:
    vocab_templates = VOCAB_NEW if not profile.core_vocab_done else VOCAB_REVIEW

    # 第三部分选择
    if analysis.weak_section == "listening":
        other_templates = LISTENING_WEAK_7
        other_label = "听力"
    elif analysis.weak_section == "writing_translation":
        other_templates = WRITING_WEAK_7
        other_label = "写译"
    else:
        other_templates = REVIEW_7
        other_label = "复习"

    days = []
    for i in range(7):
        day_num = i + 1
        days.append(DayPlan(
            day=day_num,
            vocab=vocab_templates[i],
            reading=READING_7[i],
            other=other_templates[i],
            other_label=other_label,
        ))

    # 周目标
    stage = analysis.stage
    weak_cn = SECTION_CN.get(analysis.weak_section, "") if analysis.weak_section else ""
    strong_cn = SECTION_CN.get(analysis.strong_section, "") if analysis.strong_section else ""

    if stage == "基础薄弱型":
        goal = "建立每日学习习惯，夯实词汇基础，阅读入门，每天完成三部分任务"
    elif stage == "冲线准备型":
        goal = f"稳定每日学习节奏，词汇持续积累，{'重点突破' + weak_cn if weak_cn else '均衡推进'}，向425分冲刺"
    elif stage == "接近过线型":
        goal = f"补词汇基础，{'稳住' + strong_cn if strong_cn else '稳住阅读'}，{'弱项' + weak_cn + '起步' if weak_cn else '弱项起步'}，本周不上整套"
    elif stage == "已过线提升型":
        goal = f"巩固已有优势，{'强化' + weak_cn if weak_cn else '均衡提升'}，向更高分冲刺"
    elif stage == "提优型":
        goal = f"精细化提升，{'重点攻克' + weak_cn if weak_cn else '全面提升'}，冲击高分"
    else:
        goal = "建立学习节奏，词汇+阅读双线并进，本周以分部分练习为主"

    return Week1Plan(
        student_name=profile.name,
        exam_type=profile.exam_type,
        week_goal=goal,
        days=days,
    )


# ─── GPT prompt ──────────────────────────────────────────────

def _build_gpt_prompt(profile: StudentProfile, analysis: AnalysisResult, rule_plan: Week1Plan) -> str:
    if profile.last_total_score:
        sections_info = (
            f"- 上次总分：{profile.last_total_score:.0f}\n"
            f"- 听力：{profile.last_listening or '未知'}，阅读：{profile.last_reading or '未知'}，写译：{profile.last_writing_translation or '未知'}\n"
            f"- 强项：{SECTION_CN.get(analysis.strong_section, '未知')}，弱项：{SECTION_CN.get(analysis.weak_section, '未知')}\n"
            f"- {'明显偏科（强弱差≥20分）' if analysis.is_biased else '各科差距不大'}"
        )
    else:
        sections_info = "- 无历史成绩（首次参加或未填写）"

    days_draft = ""
    for dp in rule_plan.days:
        days_draft += (
            f"\nDay{dp.day}:\n"
            f"  【单词】{dp.vocab}\n"
            f"  【阅读】{dp.reading}\n"
            f"  【{dp.other_label}】{dp.other}\n"
        )

    other_label = rule_plan.days[0].other_label

    # 根据弱项生成对应的第三部分专项说明
    if analysis.weak_section == "listening":
        third_part_rules = """### 听力专项要求（第三部分）
- Day1-3：先看烤鸭TV方法课（第1集全攻略 → 第2集核心概念 → 第3集短篇新闻题型），边看边记笔记，整理做题思路
- Day4起：开始做短新闻练习，每次1组，做完对答案，整理没听清的词和错因
- 每天听力部分必须有打卡指标，例如：打卡要交：正确题数 / 整理3条做题思路
- Day7：回顾本周笔记，重听错得最多的1组，总结仍听不出来的原因"""
    elif analysis.weak_section == "writing_translation":
        third_part_rules = """### 写译专项要求（第三部分）
- Day1-2：只读范文，不动笔写，分析段落结构和高分句型，整理可套用的句型/翻译技巧
- Day3起：开始轻量练习（写提纲+开头段 / 翻译1段），限时完成，不追求完美
- 每天写译部分必须有打卡指标，例如：打卡要交：翻译截图 / 开头段截图
- Day7：复习本周写译笔记，整理高分句型，总结最大收获"""
    else:
        third_part_rules = """### 复习专项要求（第三部分）
- 以当天单词和阅读的复习巩固为主，穿插翻译或写作轻练
- 每天复习部分要有具体记录要求，例如：整理错题 / 抄写高分句型
- Day7：复习本周全部内容，总结学习规律"""

    prompt = f"""你是一名专业的英语四六级督学老师，正在为学生制定 Week1（第一周）学习计划。

## 学生信息
- 姓名：{profile.name}
- 年级：{profile.grade or '未填写'}
- 考试类型：{profile.exam_type}
- 第几次参加：{profile.attempt_count or '首次'}
- 词汇基础：{analysis.vocab_base}
- 每日可用时间：{profile.daily_study_hours}小时{'（时间不固定，有风险）' if profile.daily_time_uncertain else ''}
- 目标分：{profile.target_score or '未填写'}
- 高考英语：{profile.gaokao_english or '未填写'}
{sections_info}

## 程序分析结果（已由规则计算，直接使用，不要自行推断）
- 分数阶段：{analysis.stage}
- 任务轻重：{analysis.task_weight}
- 目标分差评估：{analysis.score_gap_level}
- Week1 方向：{analysis.week1_focus}

## 规则草稿（请在此基础上润色，不要大幅改动结构）
{days_draft}

---

## 润色规则（严格遵守，逐条执行）

### 整体结构
1. 每天固定三部分：【单词】【阅读】【{other_label}】，顺序不变，标签不变
2. 7天要有明显递进感：Day1-2 打基础/入门 → Day3-5 练习强化 → Day6-7 复盘总结
3. 每天任务要有细微差异，不能7天完全一样

### 单词要求
4. 词汇基础为"{analysis.vocab_base}"：
   - 若"薄弱"：Day1-2 新背核心词30个，Day3起每天新背20个+复习已背词
   - 若"已有基础"：以复习巩固为主，每天快速过40个，精记生词
5. 每天单词必须包含"补充XX高频词10个"（XX根据当天主练板块选：阅读/听力/翻译/写作）
6. 每天单词必须有"要求"说明，例如：把不熟的词抄一遍 / 把最不熟的10个单独记下来

### 阅读要求（重要：A档+B档交替安排）
7. 阅读分两档：
   - A档（仔细阅读）：每次做1篇，限时15分钟，对答案，记录正确题数
   - B档（选词填空+长篇匹配）：选词填空限时10分钟 + 长篇匹配限时15分钟，同一天完成
8. 7天安排：A档出现3-4次，B档出现2-3次，Day7固定为复盘（不做新题，复习本周错题）
9. A档和B档要交替出现，不能连续3天都是A档
10. 每次阅读必须有打卡指标，例如：打卡要交：正确题数 / 错题截图

{third_part_rules}

### 语言要求
- 语气亲切自然，像督学老师写给学生的，不要太正式
- 每部分2-4行，不要太长也不要太短
- 统一用"复习单词"，不用"复盘单词"
- 统一用"听力高频词/阅读高频词"，不用"听力生词/阅读生词"
- 换行用 \\n 表示（JSON字符串内）

## 输出格式（严格按此 JSON 格式，不要有任何其他内容）
{{
  "week_goal": "本周目标一句话（20字以内，具体有方向感）",
  "days": [
    {{
      "day": 1,
      "vocab": "单词任务（含补充高频词和要求，用\\n换行）",
      "reading": "阅读任务（注明A档或B档，含打卡指标，用\\n换行）",
      "other": "{other_label}任务（含打卡指标或记录要求，用\\n换行）",
      "other_label": "{other_label}"
    }}
  ]
}}
"""
    return prompt


def _call_gpt(prompt: str) -> Optional[dict]:
    try:
        import config as _cfg
        from openai import OpenAI
        # 每次调用时重新读取，确保拿到 Streamlit secrets 注入后的最新值
        client = OpenAI(api_key=_cfg.OPENAI_API_KEY, base_url=_cfg.OPENAI_BASE_URL)
        response = client.chat.completions.create(
            model=_cfg.OPENAI_MODEL,
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
    rule_plan = _build_week1_rules(profile, analysis)

    import config as _cfg
    if use_gpt and _cfg.OPENAI_API_KEY:
        prompt = _build_gpt_prompt(profile, analysis, rule_plan)
        gpt_result = _call_gpt(prompt)
        if gpt_result:
            rule_plan = _apply_gpt_result(rule_plan, gpt_result)

    return rule_plan
