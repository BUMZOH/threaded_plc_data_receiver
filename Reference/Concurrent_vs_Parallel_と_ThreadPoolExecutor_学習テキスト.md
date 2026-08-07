# Concurrent（並行）と Parallel（並列）の違い

## はじめに

`Concurrent` と `Parallel` は似た言葉ですが、意味は異なります。

- **Concurrent（並行）** … 複数の仕事を効率よく進める考え方
- **Parallel（並列）** … 複数の仕事を本当に同時実行する考え方

この違いを理解すると、Python の `ThreadPoolExecutor` や `ProcessPoolExecutor` の役割も分かりやすくなります。

---

# Concurrent（並行）とは

## 定義

複数の処理が**重なり合う時間帯で進行している状態**です。

CPU が 1 個しかなくても実現できます。

OS が短い時間ごとに処理を切り替える（コンテキストスイッチ）ことで、

```
処理A
■■■■      ■■■■      ■■■■

処理B
    ■■■■      ■■■■
```

のように見えます。

実際には

```
A → B → A → B → A → B
```

と高速で切り替えているだけです。

人間から見ると「同時に動いている」ように感じます。

---

## 目的

Concurrent の目的は

**システム全体を止めず、効率良くタスクを管理すること**

です。

例えば

- PLC監視
- ネットワーク通信
- ファイル読み込み
- GUI操作

など、待ち時間(IO待ち)が多い処理では非常に効果があります。

---

# Parallel（並列）とは

## 定義

複数の処理を**物理的に同じ瞬間に実行すること**です。

これには

- マルチコアCPU
- 複数CPU

などのハードウェアが必要です。

例えば4コアCPUなら

```
CPU1  処理A
CPU2  処理B
CPU3  処理C
CPU4  処理D
```

のように、本当に同時に実行できます。

---

## 目的

Parallel の目的は

**重い処理を同時に実行し、全体の処理時間を短縮すること**

です。

例えば

- 画像処理
- AI
- 数値計算
- 動画変換

などです。

---

# Concurrent と Parallel の違い

|項目|Concurrent（並行）|Parallel（並列）|
|---|---|---|
|意味|仕事を切り替えながら進める|仕事を本当に同時に行う|
|CPU1個|可能|不可能|
|マルチコア|不要|必要|
|目的|待ち時間を有効活用|処理時間短縮|
|得意|通信・IO・監視|重い計算|

---

# ThreadPoolExecutor はどちら？

結論から言うと、

**ThreadPoolExecutor は「Concurrent（並行）」のための仕組み**です。

複数のスレッドを管理して、

- PLC監視
- Socket通信
- HTTP通信
- ファイル読み込み

などを効率良く実行します。

PythonではスレッドはOSスレッドですが、CPythonには **GIL (Global Interpreter Lock)** があるため、CPUを使い切る計算処理では複数スレッドが同時にPythonコードを実行できません。

そのため、CPU負荷の高い計算を高速化したい場合には向いていません。

---

# では Parallel は？

CPUをフル活用したい場合は

```python
from concurrent.futures import ProcessPoolExecutor
```

を使います。

ProcessPoolExecutor は複数のプロセスを起動するため、

- CPUコア1
- CPUコア2
- CPUコア3

を利用して本当に並列実行できます。

---

# 工場アプリで考えると

あなたが作成しているPLCアプリでは

- モータ1監視
- モータ2監視
- モータ3監視

は通信待ち(IO待ち)がほとんどです。

そのため

**ThreadPoolExecutor が最適**です。

逆に

- AI解析
- 画像認識
- FFT解析
- 大量数値演算

なら ProcessPoolExecutor の方が適しています。

---

# 覚え方

> Concurrent = 「みんなに順番に仕事を回す」

> Parallel = 「みんなが本当に同時に仕事をする」

ThreadPoolExecutor は「仕事をうまく回す監督」。

ProcessPoolExecutor は「作業員を増やして本当に同時に働く」。

このイメージで覚えると忘れにくくなります。
