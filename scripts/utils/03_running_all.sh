#!/bin/bash

# --- 設定 ---
# 実行するスクリプトのリスト（順番通りに記述）
SCRIPTS=(
    "01_nicerl2.sh"
    "03_xselect_spec.sh"
    "04_response.sh"
    "05_background.sh"
)

# ログファイル名
LOGFILE="run_all.log"

# --- 開始処理 ---
echo "=========================================="
echo " Starting Full Analysis Pipeline"
echo " Start Time: $(date)"
echo "==========================================" | tee -a "${LOGFILE}"

# 引数（-f など）をそのまま引き継ぐことを通知
if [ $# -gt 0 ]; then
    echo "Arguments passed to scripts: $@"
fi

# --- メインループ ---
for script in "${SCRIPTS[@]}"; do
    echo ""
    echo "------------------------------------------"
    echo "Running: ${script} $@"
    echo "------------------------------------------"
    
    script="scripts/${script}"
    
    # スクリプトの存在確認
    if [ ! -f "${script}" ]; then
        echo "❌ Error: Script '${script}' not found!"
        exit 1
    fi

    # 実行権限を付与 (念のため)
    chmod +x "${script}"

    # スクリプト実行
    # "$@" はこのスクリプトに渡された引数( -f 等)をそのまま渡す
    ./"${script}" "$@"

    # 直前のコマンドの終了ステータスを確認
    # 0以外ならエラーとみなして停止
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Pipeline FAILED at step: ${script}"
        echo "   Check the output above for details."
        exit 1
    fi

    echo "✅ Finished: ${script}"
done

# --- 終了処理 ---
echo ""
echo "=========================================="
echo " All scripts completed successfully!"
echo " End Time: $(date)"
echo "=========================================="