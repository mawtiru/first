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

1つの市場は1つの年・地域・計測基準・出典で統一します。確認済みの市場のみ企業詳細に表示します。上記例はデータ形式を示すもので、市場に属する各社や市場区分の妥当性も別途確認してください。

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
