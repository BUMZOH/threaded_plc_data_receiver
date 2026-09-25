# SQLite BLOB を HTTP で送るために Base64 へ変換する理由

## 1. はじめに

今回の `measurement_server` では、SQLite の `measurement_data`
テーブルに保存されているデータを Flask から HTTP
でクライアントへ送信します。

`measurement_data` の `data` 列には、波形データなどが **BLOB**
として保存されています。

SQLite から読み出した BLOB は Python では `bytes` 型になります。しかし
Flask の `jsonify()` を使って HTTP レスポンスを JSON
として返そうとすると、`bytes` 型をそのまま JSON
に変換することはできません。

実際に今回、次のエラーが発生しました。

``` text
TypeError: Object of type bytes is not JSON serializable
```

そこで、BLOB の `bytes` データを **Base64**
という文字列形式へ変換してから JSON に格納します。

この資料では、BLOB、Python の `bytes`、JSON、Base64
の関係と、なぜ今回この変換が必要だったのかを順番に整理します。

------------------------------------------------------------------------

## 2. 今回のデータの流れ

``` text
サーバPC

measurement_data.db
    ↓
SQLite BLOB
    ↓
Python bytes
    ↓
Base64へ変換
    ↓
Python str
    ↓
JSON
    ↓
HTTP
    ↓
クライアントPC
```

ポイントは、**SQLite の BLOB を JSON
で扱える文字列へ変換してから送る**ことです。

------------------------------------------------------------------------

## 3. BLOB とは

BLOB は **Binary Large Object** の略です。

SQLite
では、文字列や整数だけでなく、任意のバイナリデータを保存できます。たとえば波形データ、センサーデータ、画像、音声、圧縮データ、独自形式のバイナリなどです。

今回の `measurement_data` テーブルでは、`data` 列に波形データが BLOB
として保存されています。

``` text
id | data_name          | measured_at          | judge | data
---+--------------------+----------------------+-------+------
1  | Chuck_Air_Pressure | 2026-08-17 18:17:35 | OK    | BLOB
```

------------------------------------------------------------------------

## 4. SQLite の BLOB を Python で読むと bytes になる

Python の `sqlite3` で BLOB を読み出すと、Python 側では基本的に `bytes`
型として取得されます。

``` python
row = cursor.fetchone()
blob_data = row[4]
```

この `blob_data` は、

``` text
<class 'bytes'>
```

となります。

つまり、

``` text
SQLite BLOB
    ↓
Python bytes
```

という対応です。

------------------------------------------------------------------------

## 5. JSON は bytes を直接扱えない

JSON
が標準的に扱えるのは、文字列、数値、真偽値、null、配列、オブジェクトなどです。

一方、Python の `bytes` に直接対応する JSON のデータ型はありません。

そのため、

``` python
return jsonify(rows)
```

としたとき、取得結果に BLOB 由来の `bytes` が含まれていると Flask は
JSON へ変換できません。

今回発生した、

``` text
TypeError: Object of type bytes is not JSON serializable
```

は、「bytes 型をそのまま JSON
としてシリアライズできない」という意味です。

------------------------------------------------------------------------

## 6. 「JSON serializable」とは

`serialize`（シリアライズ）とは、データを保存や通信に使える形式へ変換することです。

たとえば Python の辞書、

``` python
data = {
    "id": 1,
    "data_name": "Chuck_Air_Pressure",
    "judge": "OK",
}
```

は JSON に変換できます。

しかし、

``` python
data = {
    "data": b"\x01\x02\x03\x04"
}
```

のように `bytes` が入ると、JSON のどの型として表現するか決められません。

そこで別の表現へ変換する必要があります。

------------------------------------------------------------------------

## 7. Base64 とは

Base64
は、**バイナリデータを文字だけで表現するためのエンコード方式**です。

今回ブラウザで確認した JSON でも、`data`
は次のような長い文字列になりました。

``` json
{
    "data": "BgAAABAAAAC7AAAAfwEAAOUBAAA2AgAA...",
    "data_name": "Chuck_Air_Pressure",
    "id": 1,
    "judge": "OK",
    "measured_at": "2026-08-17 18:17:35"
}
```

この長い文字列が、元の BLOB データを Base64 で表現したものです。

------------------------------------------------------------------------

## 8. サーバ側で行っている変換

今回追加した重要なコードは次です。

``` python
"data": base64.b64encode(row[4]).decode("ascii"),
```

処理を分解すると、

``` text
row[4]
    ↓
base64.b64encode(...)
    ↓
.decode("ascii")
```

となります。

------------------------------------------------------------------------

## 9. base64.b64encode() の役割

`row[4]` は SQLite の BLOB から取得した `bytes` です。

``` python
base64.b64encode(row[4])
```

によって Base64 形式へエンコードします。

``` text
元の bytes
    ↓
base64.b64encode()
    ↓
Base64形式の bytes
```

ここで重要なのは、**`b64encode()` しただけでは Python ではまだ `bytes`
型**という点です。

------------------------------------------------------------------------

## 10. .decode("ascii") の役割

そこで、

``` python
.decode("ascii")
```

を実行します。

``` text
Base64形式の bytes
    ↓
.decode("ascii")
    ↓
Python str
```

Python の `str` になれば JSON の文字列として扱えます。

全体では、

``` text
SQLite BLOB
    ↓
Python bytes
    ↓
base64.b64encode()
    ↓
Base64形式の bytes
    ↓
.decode("ascii")
    ↓
Python str
    ↓
jsonify()
    ↓
JSON
```

となります。

------------------------------------------------------------------------

## 11. なぜ ASCII で decode できるのか

Base64 で使用される文字は ASCII で表現できる範囲に限定されています。

主に、

``` text
A-Z
a-z
0-9
+
/
=
```

などです。

そのため、

``` python
.decode("ascii")
```

で安全に Python の文字列へ変換できます。

------------------------------------------------------------------------

## 12. なぜ Base64 にすると JSON で送れるのか

JSON から見れば、Base64 の中身が何を表しているかは関係ありません。

``` json
{
    "data": "BgAAABAAAAC7AAAAfwEAAOUBAAA2AgAA..."
}
```

JSON から見れば `data` は単なる文字列です。

したがって、

``` text
BLOB
↓
bytes
↓
Base64文字列
↓
JSON
```

と変換することで、バイナリデータを JSON の中へ格納できます。

------------------------------------------------------------------------

## 13. HTTP だから Base64 が必須なのか

ここは非常に重要です。

**HTTP そのものがバイナリを送れないわけではありません。**

HTTP ではバイナリデータそのものをレスポンスとして送ることもできます。

今回 Base64 が必要になった理由は、

> HTTP で送るデータ形式として JSON を使っており、その JSON が Python の
> `bytes` を直接表現できないから

です。

正確には、

``` text
HTTPだからBase64が必要
```

ではなく、

``` text
BLOBをJSONの中に入れて送りたい
        ↓
bytesはJSONに入らない
        ↓
Base64文字列へ変換する
```

という理由です。

------------------------------------------------------------------------

## 14. クライアント側では元に戻せる

Base64 は元のバイナリデータへ戻すことを前提としたエンコード方式です。

サーバ側では、

``` python
base64.b64encode(blob_data)
```

を使用します。

クライアント側では逆に、

``` python
base64.b64decode(base64_data)
```

とすれば元の `bytes` へ戻せます。

``` text
【サーバ】

SQLite BLOB
    ↓
bytes
    ↓
Base64
    ↓
文字列
    ↓
JSON
    ↓
HTTP

【クライアント】

HTTP
    ↓
JSON
    ↓
Base64文字列
    ↓
base64.b64decode()
    ↓
bytes
    ↓
元の波形データとして処理
```

------------------------------------------------------------------------

## 15. 今回のサーバコード

SQLite から取得した各行を辞書へ変換しています。

``` python
data = []

for row in rows:
    data.append(
        {
            "id": row[0],
            "data_name": row[1],
            "measured_at": row[2],
            "judge": row[3],
            "data": base64.b64encode(row[4]).decode("ascii"),
        }
    )

return jsonify(data)
```

通常の値はそのまま JSON へ渡し、BLOB である `data` だけ Base64
文字列へ変換しています。

つまり、**JSON にできないデータだけ JSON
で扱える形式へ変換する**という考え方です。

------------------------------------------------------------------------

## 16. Base64 のメリット

今回の構成では、JSON の構造を保ったまま BLOB
を一緒に送れるのが大きなメリットです。

``` json
{
    "id": 1,
    "data_name": "Chuck_Air_Pressure",
    "measured_at": "2026-08-17 18:17:35",
    "judge": "OK",
    "data": "BgAAABAAAAC7AAAA..."
}
```

このように、ID、データ名、測定日時、判定、波形データを同じ JSON
オブジェクトとして扱えます。

------------------------------------------------------------------------

## 17. Base64 の注意点

Base64 には、元のバイナリよりデータ量が増えるという欠点があります。

Base64 の文字列部分は、元のバイナリデータに対しておおむね約
4/3、つまり約 33% 大きくなります。さらに JSON
のキーや構文も通信量に加わります。

概算では、

``` text
元データ 3 MB
    ↓
Base64 約4 MB
```

となります。

そのため、非常に巨大なバイナリを毎回 Base64 化して JSON
で送る用途では、別方式を検討する場合があります。

今回のように SQL
で必要な測定データだけを絞り込んで取得する設計では、この点も重要です。

------------------------------------------------------------------------

## 18. Base64 は圧縮ではない

Base64 は圧縮ではありません。むしろデータ量は増えます。

``` text
Base64 = データを小さくする技術
```

ではなく、

``` text
Base64 = バイナリを文字として表現する技術
```

です。

------------------------------------------------------------------------

## 19. Base64 は暗号化でもない

Base64 は暗号化でもありません。

Base64 文字列は簡単にデコードできます。

``` text
暗号化
    → 秘密を守るための技術

Base64
    → データの表現方法を変える技術
```

したがって、Base64
にしたから通信内容が安全になるわけではありません。セキュリティが必要なら
HTTPS や認証などを別に検討します。

------------------------------------------------------------------------

## 20. 今回のエラーから理解する

最初のコードは、

``` python
rows = cursor.fetchall()

return jsonify(rows)
```

でした。

しかし `rows` の中には、

``` text
id           → int
data_name    → str
measured_at  → str
judge        → str
data         → bytes
```

が含まれていました。

`data` の `bytes` だけが JSON にできません。

そこで、

``` python
base64.b64encode(row[4]).decode("ascii")
```

によって、

``` text
data → str
```

へ変換しました。

結果として、

``` text
id           → int
data_name    → str
measured_at  → str
judge        → str
data         → str
```

となり、すべて JSON として表現できるようになりました。

これが今回エラーが解決した本質です。

------------------------------------------------------------------------

## 21. 覚えておきたいコード

### サーバ側：BLOB → Base64文字列

``` python
import base64

base64_data = base64.b64encode(blob_data).decode("ascii")
```

### クライアント側：Base64文字列 → bytes

``` python
import base64

blob_data = base64.b64decode(base64_data)
```

この2つは対になっています。

``` text
b64encode()
    ↓
通信
    ↓
b64decode()
```

------------------------------------------------------------------------

## 22. 最重要ポイント

今回の流れを一本にすると、

``` text
SQLiteのBLOB
    ↓
Pythonで読む
    ↓
bytesになる
    ↓
bytesはJSONに直接入れられない
    ↓
Base64へエンコード
    ↓
まだbytes
    ↓
decode("ascii")
    ↓
strになる
    ↓
JSONに入れられる
    ↓
HTTPでクライアントへ送信
```

クライアントでは逆に、

``` text
JSON
    ↓
Base64文字列
    ↓
base64.b64decode()
    ↓
元のbytes
```

へ戻します。

------------------------------------------------------------------------

## 23. まとめ

今回 Base64 を使用した理由は、**SQLite の BLOB を HTTP
で送るためというより、BLOB から取得した Python の `bytes` を JSON
の中に格納できる形へ変換するため**です。

``` text
SQLite BLOB
     ↓
Python bytes
     ↓
そのままではJSON化できない
     ↓
Base64
     ↓
ASCII文字列
     ↓
JSON
     ↓
HTTP
     ↓
クライアント
     ↓
Base64デコード
     ↓
元のbytes
```

今回の、

``` text
TypeError: Object of type bytes is not JSON serializable
```

というエラーは Flask や SQLite の不具合ではありません。

**SQLite の BLOB、Python の `bytes`、JSON
の文字列という、それぞれ異なるデータ表現の境界で変換が必要だった**ということです。

この「データ形式の境界では変換が必要になる」という考え方は、SQLite と
Flask に限らず、ネットワーク通信や API
を扱うときの重要な基本になります。
