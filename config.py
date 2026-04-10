# config.py - 本地配置（不会上传到 GitHub）
# Streamlit Cloud 上的配置请在 App Settings → Secrets 里填写

OPENAI_API_KEY = ""        # 本地填入，线上用 st.secrets
OPENAI_BASE_URL = "https://new.pumpkinai.vip/v1"
OPENAI_MODEL = "gpt-5.4"

# 列名关键词映射（用于模糊匹配问卷星导出的中文列名）
COLUMN_KEYWORDS = {
    "name":                    ["姓名", "名字", "学生姓名"],
    "grade":                   ["年级"],
    "exam_type":               ["四级还是六级", "四级", "六级", "参加的是"],
    "attempt_count_cet4":      ["第几次参加四级", "第几次考四级", "四级.*次"],
    "attempt_count_cet6":      ["第几次参加六级", "第几次考六级", "六级.*次"],
    "last_total_score_cet4":   ["上次四级.*总分", "四级.*总分", "四级考试的总分"],
    "last_listening_cet4":     ["四级.*听力", "听力.*四级"],
    "last_reading_cet4":       ["四级.*阅读", "阅读.*四级"],
    "last_writing_cet4":       ["四级.*写作", "写作.*四级", "写作和翻译.*四级", "四级.*写作和翻译"],
    "last_total_score_cet6":   ["上次六级.*总分", "六级.*总分", "六级考试的总分"],
    "last_listening_cet6":     ["六级.*听力", "听力.*六级"],
    "last_reading_cet6":       ["六级.*阅读", "阅读.*六级"],
    "last_writing_cet6":       ["六级.*写作", "写作.*六级", "写作翻译.*六级", "六级.*写作翻译"],
    "gaokao_english":          ["高考英语", "高考.*英语", "英语.*高考"],
    "core_vocab_done":         ["核心词", "背过.*词", "词汇"],
    "daily_study_hours":       ["每天.*时间", "可用.*时间", "复习.*时间", "学习.*时间"],
    "target_score":            ["目标分", "目标.*分数", "分数.*目标"],
}
