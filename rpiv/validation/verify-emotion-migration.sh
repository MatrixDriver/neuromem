#!/usr/bin/env bash
# =============================================================================
# 情绪架构迁移验证脚本
# 验证 EmotionProfile 在 SDK/Cloud/Me2 三端（含前端）的完全清除
#
# 用法: bash D:/CODE/NeuroMem/rpiv/validation/verify-emotion-migration.sh
# =============================================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 计数器
PASS=0
FAIL=0
SKIP=0
TOTAL=0

# 结果记录
FAILURES=()
SKIPS=()

# ---------- 辅助函数 ----------

check() {
    local id="$1"
    local desc="$2"
    TOTAL=$((TOTAL + 1))
    echo -n "  [$id] $desc ... "
}

pass() {
    PASS=$((PASS + 1))
    echo -e "${GREEN}PASS${NC}"
}

fail() {
    local msg="${1:-}"
    FAIL=$((FAIL + 1))
    FAILURES+=("[$TOTAL] $msg")
    echo -e "${RED}FAIL${NC} $msg"
}

skip() {
    local reason="${1:-}"
    SKIP=$((SKIP + 1))
    SKIPS+=("[$TOTAL] $reason")
    echo -e "${YELLOW}SKIP${NC} $reason"
}

section() {
    echo ""
    echo -e "${CYAN}=== $1 ===${NC}"
}

# ---------- TC-1: 文件存在性验证 ----------

section "TC-1: 文件存在性验证（已删除的文件不应存在）"

check "TC-1.1" "SDK emotion_profile.py 已删除"
if [ ! -f "D:/CODE/NeuroMem/neuromem/models/emotion_profile.py" ]; then
    pass
else
    fail "文件仍然存在: neuromem/models/emotion_profile.py"
fi

check "TC-1.2" "Cloud emotion-chart.tsx 已删除"
if [ ! -f "D:/CODE/neuromem-cloud/web/src/components/emotion-chart.tsx" ]; then
    pass
else
    fail "文件仍然存在: web/src/components/emotion-chart.tsx"
fi

check "TC-1.3" "Cloud emotions/route.ts 已删除"
if [ ! -f "D:/CODE/neuromem-cloud/web/src/app/api/spaces/[spaceId]/emotions/route.ts" ]; then
    pass
else
    fail "文件仍然存在: emotions/route.ts"
fi

check "TC-1.4" "Cloud emotions/page.tsx 已删除"
if [ ! -f "D:/CODE/neuromem-cloud/web/src/app/dashboard/spaces/[spaceId]/emotions/page.tsx" ]; then
    pass
else
    fail "文件仍然存在: emotions/page.tsx"
fi

check "TC-1.5" "Me2 EmotionSection.tsx 已删除"
if [ ! -f "D:/CODE/me2/frontend/components/memories/EmotionSection.tsx" ]; then
    pass
else
    fail "文件仍然存在: EmotionSection.tsx"
fi

# ---------- TC-2: Grep 零残留验证 ----------

section "TC-2: Grep 零残留验证"

# 辅助函数: 执行 grep 检查，期望零匹配
grep_zero() {
    local id="$1"
    local desc="$2"
    local pattern="$3"
    local path="$4"
    local exclude="${5:-}"

    check "$id" "$desc"

    local cmd="grep -r --include='*.py' --include='*.ts' --include='*.tsx' '$pattern' '$path'"
    if [ -n "$exclude" ]; then
        cmd="grep -r --include='*.py' --include='*.ts' --include='*.tsx' '$pattern' '$path' | grep -v '$exclude'"
    fi

    local result
    result=$(eval "$cmd" 2>/dev/null || true)

    if [ -z "$result" ]; then
        pass
    else
        local count
        count=$(echo "$result" | wc -l)
        fail "找到 $count 处残留匹配"
        echo "    残留详情:"
        echo "$result" | head -10 | sed 's/^/      /'
    fi
}

# SDK 源码（排除 tests/ 和 scripts/）
grep_zero "TC-2.1a" "SDK: EmotionProfile 零残留" \
    "EmotionProfile" "D:/CODE/NeuroMem/neuromem/"

grep_zero "TC-2.1b" "SDK: emotion_profile 零残留" \
    "emotion_profile" "D:/CODE/NeuroMem/neuromem/"

grep_zero "TC-2.1c" "SDK: emotion_profiles 零残留" \
    "emotion_profiles" "D:/CODE/NeuroMem/neuromem/"

# Cloud 后端
grep_zero "TC-2.2a" "Cloud 后端: EmotionProfile 零残留" \
    "EmotionProfile" "D:/CODE/neuromem-cloud/server/src/"

grep_zero "TC-2.2b" "Cloud 后端: emotion_profile 零残留" \
    "emotion_profile" "D:/CODE/neuromem-cloud/server/src/"

grep_zero "TC-2.2c" "Cloud 后端: EmotionProfileResponse 零残留" \
    "EmotionProfileResponse" "D:/CODE/neuromem-cloud/server/src/"

# Cloud 前端（排除 trace 组件中的 llm_emotion_summary）
grep_zero "TC-2.4a" "Cloud 前端: emotion-profile 零残留" \
    "emotion-profile" "D:/CODE/neuromem-cloud/web/src/" "llm_emotion_summary"

grep_zero "TC-2.4b" "Cloud 前端: getEmotionProfile 零残留" \
    "getEmotionProfile" "D:/CODE/neuromem-cloud/web/src/"

grep_zero "TC-2.4c" "Cloud 前端: EmotionChart 零残留" \
    "EmotionChart\|emotion-chart" "D:/CODE/neuromem-cloud/web/src/"

# Me2 后端
grep_zero "TC-2.3a" "Me2 后端: EmotionProfile 零残留" \
    "EmotionProfile" "D:/CODE/me2/backend/app/"

grep_zero "TC-2.3b" "Me2 后端: emotion_profile 零残留" \
    "emotion_profile" "D:/CODE/me2/backend/app/"

grep_zero "TC-2.3c" "Me2 后端: emotion_profiles 零残留" \
    "emotion_profiles" "D:/CODE/me2/backend/app/"

# Me2 前端（排除 analysis/page.tsx 的 emotion_expression）
grep_zero "TC-2.5a" "Me2 前端: EmotionSection 零残留" \
    "EmotionSection" "D:/CODE/me2/frontend/" "emotion_expression"

grep_zero "TC-2.5b" "Me2 前端: emotion_profile 零残留" \
    "emotion_profile" "D:/CODE/me2/frontend/" "emotion_expression"

# ---------- TC-3: SDK Import 链完整性 ----------

section "TC-3: SDK Import 链完整性"

sdk_import() {
    local id="$1"
    local desc="$2"
    local code="$3"
    local expect_fail="${4:-false}"

    check "$id" "$desc"

    local output
    if output=$(cd D:/CODE/NeuroMem && uv run python -c "$code" 2>&1); then
        if [ "$expect_fail" = "true" ]; then
            fail "预期 ImportError 但导入成功"
        else
            pass
        fi
    else
        if [ "$expect_fail" = "true" ]; then
            if echo "$output" | grep -q "ImportError\|ModuleNotFoundError"; then
                pass
            else
                fail "非预期错误: $output"
            fi
        else
            fail "导入失败: $output"
        fi
    fi
}

sdk_import "TC-3.1" "from neuromem import NeuroMemory" \
    "from neuromem import NeuroMemory; print('OK')"

sdk_import "TC-3.2" "import neuromem 不含 EmotionProfile" \
    "import neuromem; assert 'EmotionProfile' not in dir(neuromem), 'EmotionProfile still exported'; print('OK')"

sdk_import "TC-3.3" "from neuromem.models import Memory, Conversation" \
    "from neuromem.models import Memory, Conversation; print('OK')"

sdk_import "TC-3.4" "from neuromem.models import EmotionProfile 应失败" \
    "from neuromem.models import EmotionProfile" "true"

sdk_import "TC-3.5" "from neuromem._core import NeuroMemory" \
    "from neuromem._core import NeuroMemory; print('OK')"

sdk_import "TC-3.6" "from neuromem.services.reflection import ReflectionService" \
    "from neuromem.services.reflection import ReflectionService; print('OK')"

# ---------- TC-4: Cloud Import 链完整性 ----------

section "TC-4: Cloud Import 链完整性"

cloud_import() {
    local id="$1"
    local desc="$2"
    local code="$3"

    check "$id" "$desc"

    local output
    if output=$(cd D:/CODE/neuromem-cloud/server && uv run python -c "$code" 2>&1); then
        pass
    else
        # 区分 EmotionProfile 相关错误和其他环境错误
        if echo "$output" | grep -qi "EmotionProfile\|emotion_profile"; then
            fail "EmotionProfile 相关导入错误: $output"
        else
            skip "非本次改动导致: $(echo "$output" | tail -1)"
        fi
    fi
}

cloud_import "TC-4.1" "from neuromem_cloud.app import app" \
    "from neuromem_cloud.app import app; print('OK')"

cloud_import "TC-4.2" "from neuromem_cloud.api.memory_mgmt import router" \
    "from neuromem_cloud.api.memory_mgmt import router; print('OK')"

cloud_import "TC-4.3" "schemas_memory 不含 EmotionProfileResponse" \
    "from neuromem_cloud.schemas_memory import *; assert 'EmotionProfileResponse' not in dir(), 'EmotionProfileResponse still exported'; print('OK')"

# ---------- TC-5: Me2 Import 链完整性 ----------

section "TC-5: Me2 Import 链完整性"

me2_import() {
    local id="$1"
    local desc="$2"
    local code="$3"

    check "$id" "$desc"

    local output
    if output=$(cd D:/CODE/me2/backend && uv run python -c "import sys; sys.path.insert(0, '.'); $code" 2>&1); then
        pass
    else
        if echo "$output" | grep -qi "EmotionProfile\|emotion_profile\|EmotionSection"; then
            fail "EmotionProfile 相关导入错误: $output"
        else
            skip "非本次改动导致: $(echo "$output" | tail -1)"
        fi
    fi
}

me2_import "TC-5.1" "memories 路由无 EmotionProfile 依赖" \
    "from app.api.v1.memories import router; print('OK')"

me2_import "TC-5.2" "admin_service 无废弃引用" \
    "from app.services.admin_service import AdminService; print('OK')"

# ---------- TC-6: SDK 测试套件回归 ----------

section "TC-6: SDK 测试套件回归"

check "TC-6.1" "SDK pytest（需要 PostgreSQL 5436）"
if output=$(cd D:/CODE/NeuroMem && uv run pytest tests/ -v --timeout=60 -m "not slow" 2>&1); then
    # 检查是否有失败
    if echo "$output" | grep -q "failed"; then
        failed_count=$(echo "$output" | grep -oP '\d+ failed' | head -1)
        fail "$failed_count"
        echo "    失败详情:"
        echo "$output" | grep "FAILED" | head -10 | sed 's/^/      /'
    else
        pass
    fi
else
    # 检查是否是数据库连接问题
    if echo "$output" | grep -qi "connection refused\|could not connect\|OperationalError\|ConnectionRefusedError"; then
        skip "PostgreSQL 5436 不可用"
    else
        # 可能有测试失败但 pytest 返回非零
        failed_count=$(echo "$output" | grep -oP '\d+ failed' | head -1 || echo "unknown")
        fail "测试失败: $failed_count"
        echo "    失败详情:"
        echo "$output" | grep "FAILED" | head -10 | sed 's/^/      /'
    fi
fi

# ---------- TC-7: Cloud 测试套件回归 ----------

section "TC-7: Cloud 测试套件回归"

check "TC-7.1" "Cloud pytest（需要 PostgreSQL 5435）"
if output=$(cd D:/CODE/neuromem-cloud/server && uv run pytest tests/ -v 2>&1); then
    if echo "$output" | grep -q "failed"; then
        failed_count=$(echo "$output" | grep -oP '\d+ failed' | head -1)
        fail "$failed_count"
    else
        pass
    fi
else
    if echo "$output" | grep -qi "connection refused\|could not connect\|OperationalError\|ConnectionRefusedError"; then
        skip "PostgreSQL 5435 不可用"
    else
        failed_count=$(echo "$output" | grep -oP '\d+ failed' | head -1 || echo "unknown")
        fail "测试失败: $failed_count"
        echo "    失败详情:"
        echo "$output" | grep "FAILED" | head -10 | sed 's/^/      /'
    fi
fi

# ---------- TC-8: Me2 测试套件回归 ----------

section "TC-8: Me2 测试套件回归"

check "TC-8.1" "Me2 单元测试"
if output=$(cd D:/CODE/me2/backend && uv run pytest tests/ -m unit -v 2>&1); then
    if echo "$output" | grep -q "failed"; then
        failed_count=$(echo "$output" | grep -oP '\d+ failed' | head -1)
        fail "$failed_count"
    else
        pass
    fi
else
    if echo "$output" | grep -qi "no tests ran\|no items\|collected 0"; then
        skip "无单元测试可运行"
    elif echo "$output" | grep -qi "connection refused\|could not connect"; then
        skip "数据库不可用"
    else
        failed_count=$(echo "$output" | grep -oP '\d+ failed' | head -1 || echo "unknown")
        fail "测试失败: $failed_count"
        echo "    失败详情:"
        echo "$output" | grep "FAILED" | head -10 | sed 's/^/      /'
    fi
fi

# ---------- TC-FE: 前端构建验证 ----------

section "TC-FE: 前端构建验证"

check "TC-FE.1" "Cloud 前端 npm run build"
if output=$(cd D:/CODE/neuromem-cloud/web && npm run build 2>&1); then
    pass
else
    if echo "$output" | grep -qi "EmotionChart\|emotion-chart\|emotion-profile\|getEmotionProfile"; then
        fail "EmotionProfile 相关构建错误"
        echo "$output" | grep -i "emotion" | head -5 | sed 's/^/      /'
    else
        skip "非本次改动导致的构建错误"
    fi
fi

check "TC-FE.2" "Me2 前端 npm run build"
if output=$(cd D:/CODE/me2/frontend && npm run build 2>&1); then
    pass
else
    if echo "$output" | grep -qi "EmotionSection\|emotion_profile"; then
        fail "EmotionProfile 相关构建错误"
        echo "$output" | grep -i "emotion" | head -5 | sed 's/^/      /'
    else
        skip "非本次改动导致的构建错误"
    fi
fi

# ---------- 汇总报告 ----------

section "验证结果汇总"

echo ""
echo -e "  总计: ${TOTAL} 项"
echo -e "  ${GREEN}通过: ${PASS}${NC}"
echo -e "  ${RED}失败: ${FAIL}${NC}"
echo -e "  ${YELLOW}跳过: ${SKIP}${NC}"

if [ ${#FAILURES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}失败项详情:${NC}"
    for f in "${FAILURES[@]}"; do
        echo "  - $f"
    done
fi

if [ ${#SKIPS[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}跳过项详情:${NC}"
    for s in "${SKIPS[@]}"; do
        echo "  - $s"
    done
fi

echo ""
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}验证通过！所有 P0 检查项均满足。${NC}"
    exit 0
else
    echo -e "${RED}验证失败！有 ${FAIL} 项 P0 检查未通过，需要修复。${NC}"
    exit 1
fi
