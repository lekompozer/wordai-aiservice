#!/bin/bash
# ===================================================================================
# COPY & RUN - Chạy batch script trong container mà KHÔNG cần rebuild/deploy
# ===================================================================================
# Dùng khi: chỉ muốn chạy một file .py mới hoặc đã sửa trong container
#           (batch scripts, migration scripts, one-off utilities, ...)
#
# Cách dùng:
#   ./copy-and-run.sh <script.py> [arg1 arg2 ...]
#   ./copy-and-run.sh batch_translate_vi_letsread.py --from-index 50
#   ./copy-and-run.sh generate_audio_batch_letsread.py
#   ./copy-and-run.sh create_indexes.py
#
# Options đặc biệt:
#   --bg       Chạy nền (background), log ra /tmp/<script>.log
#   --log      Chỉ xem log của script đang chạy nền (không chạy lại)
#   --kill     Kill script đang chạy nền
#   --deps     Cũng copy cả thư mục src/ vào container (khi src/ có thay đổi)
# ===================================================================================

set -e

CONTAINER="ai-chatbot-rag"
DEST_DIR="/app"

# --- Parse options ---
BG=false
LOG_ONLY=false
KILL_PROC=false
COPY_SRC=false
SCRIPT=""
SCRIPT_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bg)     BG=true; shift ;;
        --log)    LOG_ONLY=true; shift ;;
        --kill)   KILL_PROC=true; shift ;;
        --deps)   COPY_SRC=true; shift ;;
        -*)       SCRIPT_ARGS+=("$1"); shift ;;
        *)
            if [[ -z "$SCRIPT" ]]; then
                SCRIPT="$1"
            else
                SCRIPT_ARGS+=("$1")
            fi
            shift ;;
    esac
done

# --- Validate ---
if [[ -z "$SCRIPT" && "$LOG_ONLY" == "false" && "$KILL_PROC" == "false" ]]; then
    echo "❌ Usage: ./copy-and-run.sh <script.py> [--bg] [--deps] [args...]"
    echo ""
    echo "   --bg      Chạy nền, log ra /tmp/<script>.log"
    echo "   --log     Xem log của script đang chạy nền"
    echo "   --kill    Kill script đang chạy nền"
    echo "   --deps    Copy cả src/ vào container (khi src/ thay đổi)"
    echo ""
    echo "Ví dụ:"
    echo "   ./copy-and-run.sh batch_translate_vi_letsread.py --bg"
    echo "   ./copy-and-run.sh generate_audio_batch_letsread.py --bg --deps"
    echo "   ./copy-and-run.sh batch_translate_vi_letsread.py --log"
    echo "   ./copy-and-run.sh batch_translate_vi_letsread.py --kill"
    exit 1
fi

SCRIPT_BASE=$(basename "$SCRIPT" .py)
LOG_FILE="/tmp/${SCRIPT_BASE}.log"

# Check container running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container '$CONTAINER' không đang chạy!"
    exit 1
fi

# --- --log: chỉ xem log ---
if [[ "$LOG_ONLY" == "true" ]]; then
    echo "📋 Log: $LOG_FILE (Ctrl+C để thoát)"
    docker exec "$CONTAINER" tail -f "$LOG_FILE" 2>/dev/null \
        || echo "⚠️  Chưa có log file. Script chưa chạy?"
    exit 0
fi

# --- --kill: kill process ---
if [[ "$KILL_PROC" == "true" ]]; then
    echo "🔪 Kill: $SCRIPT_BASE ..."
    docker exec "$CONTAINER" pkill -f "$SCRIPT_BASE" 2>/dev/null && echo "✅ Killed" || echo "⚠️  Không tìm thấy process"
    exit 0
fi

# --- Validate script file ---
if [[ ! -f "$SCRIPT" ]]; then
    echo "❌ File không tồn tại: $SCRIPT"
    exit 1
fi

echo "📦 copy-and-run: $SCRIPT"
echo "   Container : $CONTAINER"
[[ "$BG" == "true" ]] && echo "   Mode      : background (log → $LOG_FILE)" || echo "   Mode      : foreground"
[[ ${#SCRIPT_ARGS[@]} -gt 0 ]] && echo "   Args      : ${SCRIPT_ARGS[*]}"
echo ""

# --- Copy script ---
docker cp "$SCRIPT" "${CONTAINER}:${DEST_DIR}/$(basename "$SCRIPT")"
echo "✅ Copied: $SCRIPT → ${DEST_DIR}/$(basename "$SCRIPT")"

# --- Optional: copy src/ cho trường hợp service/utils thay đổi ---
if [[ "$COPY_SRC" == "true" ]]; then
    echo "📂 Copying src/ ..."
    docker cp src/ "${CONTAINER}:${DEST_DIR}/src"
    echo "✅ Copied: src/"
fi

# --- Chạy script ---
CMD="python3 ${DEST_DIR}/$(basename "$SCRIPT") ${SCRIPT_ARGS[*]}"

if [[ "$BG" == "true" ]]; then
    # Chạy nền: dùng nohup trong container, log ra file
    docker exec -d "$CONTAINER" bash -c \
        "nohup $CMD > $LOG_FILE 2>&1"
    echo "🚀 Đang chạy nền! Xem log:"
    echo "   ./copy-and-run.sh $SCRIPT --log"
    echo "   hoặc: docker exec $CONTAINER tail -f $LOG_FILE"
else
    # Chạy foreground: output thẳng ra terminal
    echo "🚀 Running..."
    echo "═══════════════════════════════════════════════════════════"
    docker exec -it "$CONTAINER" bash -c "$CMD"
    echo "═══════════════════════════════════════════════════════════"
    echo "✅ Done!"
fi
