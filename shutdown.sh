#!/bin/bash
# /opt/catagent/shutdown.sh — MiaoAgent 关机前执行
# 用法：/opt/catagent/shutdown.sh

echo "==========================================="
echo "  MiaoAgent 关机流程"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="

# 1. Git 提交
echo ""
echo "[1/2] 提交代码..."
cd /opt/catagent
if git diff --quiet && git diff --cached --quiet; then
    echo "  没有未提交的更改"
else
    git add -A
    COMMIT_MSG="auto-save $(date '+%m-%d %H:%M')"
    git commit -m "$COMMIT_MSG"
    echo "  ✓ 已提交: $COMMIT_MSG"
fi

# 2. 显示今日工作统计
echo ""
echo "[2/2] 今日 Git 统计："
echo "  提交次数: $(git log --since='6:30' --oneline | wc -l)"
echo "  修改文件: $(git diff --stat HEAD~1 2>/dev/null | tail -1)"

echo ""
echo "==========================================="
echo "  ✓ 可以安全断电了"
echo "  明天开机执行: /opt/catagent/start.sh"
echo "==========================================="
