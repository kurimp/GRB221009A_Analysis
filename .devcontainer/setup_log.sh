#!/bin/bash

export TZ=Asia/Tokyo

# ログ保存用ディレクトリ
LOG_DIR="/workspaces/HEASoft/terminal_logs"

if [ ! -d "$LOG_DIR" ]; then
  mkdir -p "$LOG_DIR"
fi

if [[ $- == *i* ]] && [[ -z "$SCRIPT_LOGGING" ]]; then
  export SCRIPT_LOGGING="true"

  TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
  RAW_LOG="$LOG_DIR/${TIMESTAMP}_raw.log"
  CLEAN_LOG="$LOG_DIR/${TIMESTAMP}.log"

  echo "--- Logging Session Started: $RAW_LOG ---"

  script -q -a "$RAW_LOG" -c "/bin/bash"

  if [ -f "$RAW_LOG" ]; then
    echo "Processing log..."

    # ========================================================
    # 修正箇所: sed の囲みをダブルクォート(")からシングルクォート(')に変更
    # ========================================================
    cat "$RAW_LOG" | \
      # 1. scriptコマンドが付けるヘッダー・フッター行を削除
      sed '/Script started on/d' | \
      sed '/Script done on/d' | \
      # 2. 制御文字除去（修正点: [0-9;?]* にして '?' を許可）
      #    これで ?2004h や exit4l のゴミが消えます
      sed -r 's/\x1B\[[0-9;?]*[a-zA-Z]//g' | \
      # 3. ウィンドウタイトル設定などのOSC制御文字を除去
      sed -r 's/\x1B\][0-9];.*(\x07|\x1B\\)//g' | \
      # 4. 行末のキャリッジリターンを除去
      sed -r 's/\r$//g' | \
      # 5. バックスペース処理とタブ整形
      col -bx > "$CLEAN_LOG"

    rm "$RAW_LOG"
    echo "--- Log Saved: $CLEAN_LOG ---"
  else
    echo "Error: Raw log file was not created."
  fi
  exit
fi