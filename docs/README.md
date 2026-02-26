# NICERによる輝線解析のためのファイル群の使い方

このファイル群は、2025年度B4の栗原の卒業研究において作成した解析環境を流用するためのものです。

## 想定するdirectory構造

以下の構造を厳密に守ってください。GithubからCloneした場合、この一部が既に再現されます。

``` text
HEASoft
├─ .devcontainer
│   ├─ .alias
│   ├─ devcontainer.json
│   └─ Dockerfile
├─ .venv
│   └─ ...
├─ CALDB
│   └─ data
│       ├─ gen
│       │   └─ ...
│       ├─ nicer
│       │   └─ ...
│       └─ software
│           └─ ...
├─ data
│   ├─ collect
│   │   └─ ...
│   ├─ obs
│   │   └─ [obsID]
│   │       └─ ...
│   └─ seg
│       └─ [segID]
│           └─ ...
├─ lists
│   ├─ [group name]
│   │   └─ [name].csv
│   └─ ...
├─ results
│   └─ ...
├─ scripts
│   ├─ utils
│   │   └─ ...
│   ├─ ...
│   └─ config.yaml
├─ .gitignore
└─ requirement.txt
```

## 使用場面別の操作方法

### NICERのデータのダウンロードからLight curveとSpectrumの抽出

#### データのダウンロード

NICERの観測データをダウンロードします。[HEASARC Browse](https://heasarc.gsfc.nasa.gov/cgi-bin/W3Browse/w3browse.pl)から目標の天体を探してください。
今回は例としてGRB 221009Aを使います。「1. Do you want to search around a position ... ?」の「Object Name or Coordinates」に「GRB221009A」を、「2. What missions and catalogs do you want to search?」の「NICER」にチェックを入れ、画面上部の「Start Search」を押してください。

![Spectrum](images/HEASARC-01.png)

画面上部「Query Results」から、ダウンロードするファイルをSelectして画面下部「Retrieve Data Products for selected rows」を押します。ファイルは大きいため、扱いやすさの観点(とCLIに慣れるため)から「Create Download Scripts」を押し、「Download Commands To File」しましょう。
Downloadしたのはscriptファイルです。これを実行する必要があります。このファイルを、`HEASoft/data/obs/`に置きます。

```text
HEASoft/
├─ data/
│ └─ obs/
│   └─ browse_download_script.txt
└─ ...
```

CLIを操作します。Devcontainerの機能より、カレントディレクトリは`HEASoft/`になっているはずです。ここで、

```bash
cd data/obs
bash browse_download_script.txt
```

を実行します。選択したデータが`obs/`直下にダウンロードされます。大きなファイルであるため長い時間がかかることが想定されます。ダウンロードが終わったら、

```bash
cd ../..
```

でカレントディレクトリを`HEASoft/`に戻すのを忘れずに。

#### nicerl2の実行

nicerl2を実行します。
まず、ObsIDのリストを作成します。`HEASoft/lists/`直下に、観測に用いるObsIDを下記のように列挙した`obs_list.txt`を作成してください。

```text
5420250101
5420250102
5410670101
5410670102
5410670103
```

以下のようにして`01_nicerl2.sh`を実行します。カレントディレクトリが`HEASoft/`であることを確認してください。

```bash
bash scripts/01_nicerl2.sh
```

#### Light curveの抽出とファイル集め、表示

Light curveを抽出します。
まずは設定から。`HEASoft/scripts/config.yaml`を開き、以下のパラメーターを設定してください。

|名前|意味|入力例|例の意味|
|:---|:---|:---|:---|
|general.parameters.BIN|何秒でbinningするか(s)|120|120秒間をまとめて1つのデータ点に。|
|general.parameters.PI_MIN|含める最低のチャンネルはいくつか|30|$0.3\,\mathrm{keV}$以上のデータを含める。|
|general.parameters.PI_MAX|含める最高のチャンネルはいくつか|1000|$10\,\mathrm{keV}$以下のデータを含める。|

設定を終えたら、以下のようにして`01_nicerl2.sh`を実行します。カレントディレクトリが`HEASoft/`であることを確認してください。Light curveの抽出は、`HEASoft/lists/obs_list.txt`に書かれた全てのObsIDについて行います。

```bash
bash scripts/02_xselect-lc.sh
```

作成されたLight curveデータが書き込まれた`.lc`ファイルは、`HEASoft/data/obs/[obsID]`の直下に`ni[obsID]_src_bin[BIN]_from[PI_MIN]to[PI_MAX].lc`という名前でできます。

作成された`.lc`をplotするために、まずはデータを1つのdirectoryに集めます。`HEASoft/scripts/config.yaml`を開き、以下のパラメーターを設定してください。BIN、PI_MAX、PI_MINは先と同様です。

|名前|意味|入力例|例の意味|
|:---|:---|:---|:---|
|segment.parameters.is_obs_seg|obsIDか、segIDか|obs|obsIDに対して処理を行う。|
|segment.parameters.collect_dir|`.lc`をどこにあつめるか指定する|`obs`|`data/collect/obs/`に`.lc`をあつめる。|

設定を終えたら、以下のようにして`10_collect-data.sh`を実行します。カレントディレクトリが`HEASoft/`であることを確認してください。`.lc`の収集は、`HEASoft/lists/obs_list.txt`に書かれた全てのObsIDについて行います。

```bash
bash scripts/10_collect-data.sh
```

収集された`.lc`ファイルは、`data/collect/[collect_dir]/bin[BIN]/from[PI_MIN]to[PI_MAX]/`直下にあります。

Light curveのplotを行います。`HEASoft/scripts/config.yaml`を開き、以下のパラメーターを設定してください。BIN、PI_MAX、PI_MIN、collect_dirは先と同様です。

|名前|意味|入力例|例の意味|
|:---|:---|:---|:---|
|lightcurve.parameters.lc_xmin|plotするx(時間)の最小値を指定する|10000|$10000\,\mathrm{s}$より大きい範囲についてplotする。|
|lightcurve.parameters.lc_xmax|plotするx(時間)の最大値を指定する|3000000|$3000000\,\mathrm{s}$より小さい範囲についてplotする。|
|lightcurve.parameters.lc_ymin|plotするy(rate)の最小値を指定する|0.01|$0.01\,\mathrm{counts/s}$より大きい範囲についてplotする。|
|lightcurve.parameters.lc_ymax|plotするy(rate)の最大値を指定する|100|$100\,\mathrm{counts/s}$より小さい範囲についてplotする。|
|general.parameters.trigger_time|現象のtrigger時刻(MJD)を指定する|59861.55347211|2022-10-09 13:16:59.990 UTCをtrigger時刻に設定する。|

設定を終えたら、以下のようにして`11-1_lightcurve-seg.py`を実行します。カレントディレクトリが`HEASoft/`であることを確認してください。

```bash
python scripts/11-1_lightcurve-seg.py
```

実行すると、CLI上でこの2つが訊かれます。

```bash
Enter 1 for analysis per segID, or 0 otherwise (default is 1).:
Enter 1 to perform fitting, or 0 otherwise (default is 0).:
```

1つめは、plotをObsID(SegID)ごとにまとめてplotするか、`nicerl2`で行ったbinningによる点でplotするかです。空欄のままenterするとObsID(SegID)ごとにします。
2つめは、データ点をfittingするかどうかです。空欄のままenterするとfittingしません。1にするとfittingを行います。直後に

```bash
Enter 1 to use Broken Power Law Model, or 0 Power Law Model (default is 0).:
```

と訊かれますので、modelをBroken Power Lawにするなら1を、Power Lawにするなら0を入力してください。

成果物は、`results/lightcurve/[collect_dir]/bin[BIN]/from[PI_MIN]to[PI_MAX]/`直下にあります。成果物は以下の3種類です。

|名前|内容|
|:---|:---|
|data.csv|各データ点の時刻、rate、そしてそのerrorの情報が書かれたもの。|
|segID.png / Indiv.png|plotの画像ファイル。ObsID(SegID)ごとにまとめてplotの場合は前者が、`nicerl2`で行ったbinningによる点でplotの場合は後者が出力される。|
|ObsInfo.csv|各データ点のObsID(SegID)、観測開始の時刻、観測終了の時刻、exposureの情報が書かれたもの。|

![Spectrum](images/lc.png)
*GRB 221009Aについて、これまでの入力例の設定で出力したplot(各点は`nicerl2`で行ったbinningによる点)。*
