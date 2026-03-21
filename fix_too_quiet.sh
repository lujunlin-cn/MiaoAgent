#!/bin/bash
# /opt/catagent/fix_too_quiet.sh
# 修复猫咪"老是不说话"的问题
# 原因：决策 prompt 太保守，看到 neutral 就不开口
# 修复：调整 prompt 让它更主动

cd /opt/catagent

# 备份
cp skills/proactive_engine/engine_v2.py skills/proactive_engine/engine_v2.py.bak

# 替换 FUSION_JUDGE_PROMPT
python3 << 'PYTHON_SCRIPT'
import re

filepath = "skills/proactive_engine/engine_v2.py"
with open(filepath, "r") as f:
    content = f.read()

old_prompt_start = 'FUSION_JUDGE_PROMPT = """'
old_prompt_end = '"""'

# Find and replace the prompt
new_prompt = '''FUSION_JUDGE_PROMPT = """You are the emotional decision engine for MiaoJiang, an AI cat companion.
You receive independent signals from perception models. Your job is to decide if MiaoJiang should speak.

IMPORTANT GUIDELINES:
1. You are a caring cat companion. When in doubt, LEAN TOWARDS speaking.
   A gentle "are you okay?" is almost never harmful, but missing someone who needs comfort IS harmful.
2. "neutral + tired" = the cat SHOULD check in gently
3. "negative from ANY source" = the cat SHOULD speak
4. Only stay silent if the user genuinely seems fine (positive/neutral from ALL sources)
   OR if they explicitly asked to be left alone
5. Late night (23:00-05:00): always do a gentle reminder
6. Sedentary > 2 hours: always do a gentle reminder
7. When signals conflict, trust the MORE negative signal (better safe than sorry)

Output ONLY JSON:
{
    "reasoning": "2-3 sentences explaining your decision, in Chinese",
    "emotion": "happy/neutral/sad/tired/anxious/frustrated",
    "confidence": 0.0-1.0,
    "should_speak": true/false,
    "speak_reason": "why, in Chinese",
    "strategy": "empathetic_listening/encouragement/distraction/gentle_reminder/silent_comfort",
    "opener": "opening line in Chinese, cat personality, max 1 sentence",
    "cat_state": "neutral_idle/concerned/sleepy/sad_empathy/curious/encouraging/silent_comfort"
}"""'''

# Replace the old prompt
start_idx = content.find('FUSION_JUDGE_PROMPT = """')
if start_idx == -1:
    print("ERROR: Could not find FUSION_JUDGE_PROMPT")
    exit(1)

# Find the closing triple quotes after the prompt
end_search_start = start_idx + len('FUSION_JUDGE_PROMPT = """')
end_idx = content.find('"""', end_search_start)
if end_idx == -1:
    print("ERROR: Could not find end of prompt")
    exit(1)
end_idx += 3  # include the closing """

content = content[:start_idx] + new_prompt + content[end_idx:]

with open(filepath, "w") as f:
    f.write(content)

print("✓ FUSION_JUDGE_PROMPT updated successfully")
print("  Cat will now lean towards speaking when signals are ambiguous")
PYTHON_SCRIPT

# 同时降低触发门槛：1个信号源就够（之前要2个）
# 这样摄像头单独检测到 tired 就能触发决策
python3 << 'PYTHON_SCRIPT2'
filepath = "skills/proactive_engine/engine_v2.py"
with open(filepath, "r") as f:
    content = f.read()

# Change min_sources from 2 to 1
content = content.replace(
    "if not store.has_multi_source_events(minutes=30, min_sources=2):",
    "if not store.has_multi_source_events(minutes=30, min_sources=1):"
)
content = content.replace(
    'f"only {src_count} source(s), need >= 2"',
    'f"only {src_count} source(s), need >= 1"'
)

with open(filepath, "w") as f:
    f.write(content)

print("✓ Trigger threshold lowered: 1 source is enough")
print("  Camera alone can now trigger proactive decision")
PYTHON_SCRIPT2

echo ""
echo "修复完成！重新运行 python3 main_v2.py 测试"
echo "摄像头检测到 tired/negative 时，猫咪应该会主动说话了"
