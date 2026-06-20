# card-manager-html

クレジットカード明細CSVを読み込んで、無料で見られるHTMLレポートを作るローカルツールです。

- Excel不要
- Google Cloud設定不要
- ブラウザで閲覧可能
- 楽天カード / PayPayカードのCSVを想定
- カテゴリ分類ルールはCSVで編集可能

## フォルダ構成

```text
card-manager-html/
├─ input/
│  ├─ rakuten/      # 楽天カードCSVを置く
│  └─ paypay/       # PayPayカードCSVを置く
├─ samples/          # GitHubで共有するサンプルCSV
│  ├─ rakuten/
│  └─ paypay/
├─ archive/         # 取込済みCSVの退避先
├─ config/
│  ├─ category_rules.csv
│  └─ settings.json
├─ output/
│  ├─ report.html
│  └─ merged_transactions.csv
├─ src/
│  ├─ main.py
│  ├─ csv_loader.py
│  ├─ category.py
│  ├─ report.py
│  ├─ config.py
│  └─ utils.py
└─ requirements.txt
```

## セットアップ

```bash
cd card-manager-html
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 使い方

1. 楽天カードCSVを `input/rakuten/` に置く
2. PayPayカードCSVを `input/paypay/` に置く
3. 実行する

```bash
python src/main.py
```

4. `output/report.html` をブラウザで開く

実行後、生成されたHTMLレポートは既定のブラウザで自動的に開きます。自動で
開きたくない場合は、`config/settings.json` の
`open_report_after_generation` を `false` に変更してください。

入力形式を確認したい場合は `samples/` のCSVを参照してください。サンプルは
集計対象の `input/` とは分離されています。

## カテゴリ分類を増やす

`config/category_rules.csv` を編集します。

```csv
keyword,category
Amazon,ネット通販
イオン,食費
ENEOS,車・ガソリン
```

店舗名に `keyword` が含まれていたら、その `category` に分類します。

個人的な店舗名や地域が分かるルールは `config/category_rules.local.csv` に
記載してください。このファイルも同じ `keyword,category` 形式で読み込まれ、
GitHubにはアップロードされません。

## CSV列名が合わない場合

カード会社のCSV列名が違う場合は、`config/settings.json` の候補列名を追加してください。

例:

```json
"rakuten": {
  "date_columns": ["利用日", "利用年月日", "ご利用日"],
  "shop_columns": ["利用店名・商品名", "利用店名", "ご利用先"],
  "amount_columns": ["利用金額", "ご利用金額", "金額"]
}
```

## 取込後にCSVをarchiveへ移動したい場合

`config/settings.json` の以下を変更します。

```json
"archive_after_import": true
```

最初は `false` のままがおすすめです。

## 注意

実際の楽天カード/PayPayカードCSVは列名や文字コードが変わる可能性があります。エラーが出た場合は、表示された「実際の列」を見て `settings.json` に列名を追加してください。
