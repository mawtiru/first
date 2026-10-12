# 確認済みデータの登録形式

以下は構造説明用です。実際の数値や出典ではありません。`example.test` のURLと例示値を実データへ変更し、公式資料の該当ページを確認してから `verified` にしてください。

## 財務値

`site/data/research.json` の `finance` に企業IDをキーとして追加します。

```json
{
  "tel": {
    "period": "対象会計年度",
    "segment": "半導体関連部門名",
    "basis": "日本基準・営業利益（部門と全社で同じ利益定義）",
    "unit": "億円",
    "sourceUrl": "https://example.test/official-results.pdf",
    "verifiedAt": "確認日 YYYY-MM-DD",
    "note": "集計範囲、資料ページ、全社調整の説明",
    "sales": {"status": "unverified", "segment": null, "total": null},
    "operatingProfit": {"status": "undisclosed", "segment": null, "total": null}
  }
}
```

状態は `verified`（確認済み）、`undisclosed`（非開示を確認）、`unverified`（未確認）。確認済みの項目には `segment`（半導体部門）と `total`（全社）の数値を登録します。比率は表示時に計算し、生の割合を別途手入力しません。売上ゼロ、全社営業利益ゼロ、赤字、100%超を区別します。

## 製品市場シェア

`markets` 配列に次の形で追加します。

```json
{
  "id": "lithography-world-year",
  "status": "unverified",
  "product": "製品市場名",
  "year": 2025,
  "region": "世界",
  "measure": "売上金額ベース",
  "definition": "対象製品の範囲と除外項目",
  "sourceUrl": "https://example.test/market-report",
  "verifiedAt": "確認日 YYYY-MM-DD",
  "note": "資料のページ、集計方法、丸め等",
  "rows": [
    {"companyId": "asml", "share": null},
    {"companyId": "nikon", "share": null},
    {"name": "その他", "share": null}
  ]
}
```

1つの市場は1つの年・地域・計測基準・出典で統一します。確認済み（verified）と出典元の推計（estimated）の市場を企業詳細に表示します。estimatedにも出典・対象年・地域・集計基準・確認日を必須とし、noteに推計方法と未検証の範囲を記録します。画面では推計値と明示します。上記例はデータ形式を示すもので、市場に属する各社や市場区分の妥当性も別途確認してください。

## 適時開示

`disclosures` に企業IDをキーとして配列を追加します。

```json
{
  "tel": [
    {
      "id": "一意のID",
      "status": "unverified",
      "title": "正式な開示見出し",
      "publisher": "発表企業名",
      "url": "https://example.test/official-disclosure.pdf",
      "publishedAt": "2026-10-10T06:00:00Z",
      "retrievedAt": "2026-10-10T07:00:00Z",
      "relevance": "開示の確認元・種類・原資料ページ"
    }
  ]
}
```

日時はISO 8601で、表示時に日本時間へ変換されます。確認済みだけが正式な適時開示欄に表示されます。

## 企業概要と生産拠点

`catalog.json` の企業レコードに `profile`、`listing`、`facilities`、`marketCapSource` を登録します。

- `profile`：summary（事業説明）、industryPosition（業界内の役割）、strengths（技術分野）、informationStatus（reference / verified）、sourceUrl、verifiedAt、note。
- `listing`：status（listed / private / subsidiary）、ticker、exchange、parent、note。親会社の銘柄を非上場子会社に登録しないでください。
- `facilities`：name、location（国・都市）、function（生産機能）、kind（manufacturing_candidate / manufacturing / rd）、status（unverified / verified）、sourceUrl、verifiedAt。確認できた工場は kind を manufacturing にしてください。工場と本社・研究所を混同しないでください。地図は登録した名称と所在地を使う検索リンクであり、座標を検証したピンではありません。
- `marketCapSource`：provider（companiesmarketcap）、slug（企業ページのURL部分）、ticker（取得元ページタイトルにある銘柄）。非上場企業はnullです。市場価値の数値は自動収集先である `updates.json` の companies[企業ID].marketCap に保存されます。

確認済みに変更する場合は、対象事実を確認できる公式資料のURLと確認日を併記してください。一般の公式トップページへのリンクだけで確認済みとしないでください。

### 共通設備・インフラ

`catalog.infrastructure` は工程の順序を持たない独立項目です。企業の `infrastructureIds` から参照します。搬送・水処理専業の企業は `stageIds: []` とし、実際の工程装置も扱う企業は両方を指定できます。企業には少なくとも一つの工程または共通設備の所属が必要です。トップと `#/infrastructure/<id>` に表示し、企業詳細へのリンクは `?infrastructure=<id>` で戻り先を保持します。ニュース等の日次収集は所属に関わらず全企業が対象です。

### 項目ごとの分類

`category` は企業の主分類。`stageCategories` と `infrastructureCategories` は所属項目ID→分類の上書きで、装置・部品・材料を併営する企業に使用。所属外のIDと不正な分類は検証で拒否する。分類は `equipment`、`parts`、`materials`、`services`。各項目の一覧・件数・フィルターはその項目の分類を使用し、トップの全企業検索は主分類を使用。企業詳細の項目リンクには分類を併記する。
