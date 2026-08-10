
# GIL（Global Interpreter Lock）とは何か
## 図解で理解するPythonマルチスレッド

---

# はじめに

PythonでThreadPoolExecutorを学ぶと、必ず登場するのが **GIL（Global Interpreter Lock）** です。

「スレッドは複数あるのに、なぜCPUを使う計算は速くならないのか？」

その理由がGILです。

この資料では、初心者向けに図を使って順番に説明します。

---

# GILとは？

GIL（Global Interpreter Lock）は、

**「Pythonコードを実行できるスレッドは、一度に1つだけ」というルール**です。

このルールは、標準的なPython実装である **CPython** にあります。

---

# スレッドは本当に作られている

ThreadPoolExecutorを使うと

```python
from concurrent.futures import ThreadPoolExecutor
```

OS上には本物のスレッドが作られます。

```
Windows

├── Thread1
├── Thread2
└── Thread3
```

ここまでは普通のマルチスレッドです。

---

# しかしGILがある

Pythonコードを実行すると

```
          +----------------------+
Thread1 → |      GILの門        | → Python実行
Thread2 → |  通れるのは1人だけ  |
Thread3 → |                      |
          +----------------------+
```

GILが「入場券」の役割をしているため、

同時にPythonコードを実行できるのは1スレッドだけです。

---

# 実際にはどう動く？

例えば3つの仕事

```
仕事A
仕事B
仕事C
```

を登録すると

```
Thread1 実行

Thread2 待機

Thread3 待機
```

ではありません。

実際には

```
Thread1 実行

↓

Thread2 実行

↓

Thread3 実行

↓

Thread1 実行

↓

Thread2 実行
```

というように高速で交代しています。

これを **コンテキストスイッチ** と呼びます。

人間には同時に動いているように見えます。

---

# CPU計算が速くならない理由

例えば

```python
def work():
    total = 0
    for i in range(500_000_000):
        total += i
```

を3スレッドで実行しても

```
Thread1 ========

Thread2     ========

Thread3         ========
```

のように順番にCPUを使うため、

期待するほど高速化されません。

---

# PLC通信では問題ない理由

PLC通信は

```
送信

↓

PLCの返事待ち（50ms）

↓

受信
```

という流れです。

返事待ちの間は

```
CPU
↓

何もしていない
```

状態になります。

するとPythonは

```
Motor1 待機中

↓

Motor2 通信開始

↓

Motor3 通信開始
```

というように別スレッドへ切り替えます。

つまり

**待ち時間を有効利用できる**ため、ThreadPoolExecutorが非常に効果的です。

---

# ThreadPoolExecutor と ProcessPoolExecutor

```
ThreadPoolExecutor

Thread1
Thread2
Thread3

      │
      ▼

     GIL

      │

Pythonコードは1つずつ
```

一方

```
ProcessPoolExecutor

Process1 → Python → GIL①

Process2 → Python → GIL②

Process3 → Python → GIL③
```

プロセスごとにPythonが独立しているため、

CPUコアを使って本当に並列実行できます。

---

# ConcurrentとParallelとの関係

```
Concurrent（並行）

Thread1
 ↓
Thread2
 ↓
Thread3

順番に切り替えながら進める
```

```
Parallel（並列）

CPU1 → Thread1

CPU2 → Thread2

CPU3 → Thread3

本当に同時に実行
```

ThreadPoolExecutorは主にConcurrent向け、

ProcessPoolExecutorはParallel向けです。

---

# PLCアプリで考える

現在作成しているモータ電流受信アプリでは

```
Motor1通信

Motor2通信

Motor3通信
```

の大半が通信待ちです。

そのため

- GILはほとんど問題にならない
- ThreadPoolExecutorが最適

という結論になります。

---

# GILのメリット

- Python内部のデータを安全に扱える
- インタプリタの実装が比較的シンプル
- シングルスレッド性能が高い

---

# GILのデメリット

- CPU負荷の高い計算はマルチスレッドで高速化しにくい
- AI・画像処理・数値計算では不利

---

# 実務での使い分け

|処理|おすすめ|
|---|---|
|PLC通信|ThreadPoolExecutor|
|HTTP通信|ThreadPoolExecutor|
|ファイル読み込み|ThreadPoolExecutor|
|SQLiteアクセス（I/O中心）|ThreadPoolExecutor|
|画像処理|ProcessPoolExecutor|
|AI・機械学習|ProcessPoolExecutor|
|FFT・大量演算|ProcessPoolExecutor|

---

# 覚え方

> **GIL = 「Pythonコード実行の入場券」**

> **ThreadPoolExecutor = 待ち時間を有効活用する仕組み**

> **ProcessPoolExecutor = CPUをフル活用する仕組み**

この3つをセットで覚えると、Pythonのマルチスレッド・マルチプロセスの考え方が整理できます。
