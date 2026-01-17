import os

# 設定
input_file = 'seglist_indiv.csv'
output_dir = 'scripts/individual_csvs'

# 保存先ディレクトリの作成
if not os.path.exists(output_dir):
  os.makedirs(output_dir)

with open(input_file, 'r') as f:
  # 実際に処理した行をカウントするための変数
  count = 0
  for line in f:
    clean_line = line.strip()

    if clean_line:
      # カウントを1増やす（1から始めたい場合はここを調整）
      count += 1

      ids = [id.strip() for id in clean_line.split(',')]

      # ファイル名は 3桁(001〜)で固定
      file_name = f"seglist_indiv{count:03d}.csv"
      output_path = os.path.join(output_dir, file_name)

      with open(output_path, 'w') as f_out:
        # リスト内のIDを1つずつ「改行」を付けて書き込む
        for individual_id in ids:
          f_out.write(individual_id + '\n')

      print(f"[{count:03d}] 作成完了: {output_path} (ID数: {len(ids)})")

print(f"\n完了！合計 {count} 件のCSVファイルを '{output_dir}' 内に作成しました。")