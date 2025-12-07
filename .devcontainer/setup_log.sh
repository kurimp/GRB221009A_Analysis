#!/bin/bash

export TZ=Asia/Tokyo

# ログ保存用ディレクトリ
LOG_DIR="terminal_logs"
if [ ! -d "$LOG_DIR" ]; then
  mkdir -p "$LOG_DIR"
fi

# インタラクティブモードで、かつまだログ記録中でなければ script を起動
if [[ $- == *i* ]] && [[ -z "$SCRIPT_LOGGING" ]]; then
  export SCRIPT_LOGGING="true"
  
  # ファイル名の定義
  TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
  RAW_LOG="$LOG_DIR/${TIMESTAMP}_raw.log"   # 元の色付きログ
  CLEAN_LOG="$LOG_DIR/${TIMESTAMP}.log"     # 完成する綺麗なログ

  echo "--- Session Log Started: $CLEAN_LOG ---"
  
  # 1. まずは通常通りログを記録 (一時ファイル _raw.log に保存)
  script -q -a "$RAW_LOG" -c "/bin/bash"
  
  # 2. セッション終了後、自動的に制御文字を除去してメインのログファイルに保存
  # (色コード除去 + 行末のキャリッジリターン除去)
  sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g" "$RAW_LOG" | sed 's/\r$//' > "$CLEAN_LOG"
  
  # 3. 元の色付きログが不要なら削除する (残したい場合はコメントアウトしてください)
  # rm "$RAW_LOG"
  
  echo "--- Log saved (cleaned): $CLEAN_LOG ---"
  exit
fi

# 2. ログを色付きのまま綺麗に読むためのエイリアス
# 使い方: viewlog terminal_logs/xxxxx.log
alias viewlog='less -R'