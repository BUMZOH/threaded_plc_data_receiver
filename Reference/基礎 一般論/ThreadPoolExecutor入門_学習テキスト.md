
# ThreadPoolExecutor 入門
Python初心者向け学習テキスト

---

# はじめに

`ThreadPoolExecutor` は、Pythonでマルチスレッド処理を簡単に書くための仕組みです。

工場のPLC通信やネットワーク通信、ファイル読み込みなど、
「待ち時間（I/O待ち）」が多い処理で非常に活躍します。

あなたが作成しているPLCのモータ電流受信アプリでも最適な選択肢です。

---

# ThreadPoolExecutorとは

ThreadPoolExecutorは、

「一定数の作業員（スレッド）をあらかじめ用意し、
仕事が来たら順番に割り当てる仕組み」

です。

イメージ

                ThreadPoolExecutor
        +-----------------------------+
        | Worker1                     |
仕事A -->|                             |
        | Worker2                     |
仕事B -->|                             |
        | Worker3                     |
仕事C -->|                             |
        +-----------------------------+

毎回スレッドを作るのではなく、使い回すため高速で効率的です。

---

# Thread（スレッド）とは

プログラムの中で同時進行できる「作業員」です。

例えば

- PLC監視
- ログ保存
- ファイル読み込み

などを別々に担当できます。

---

# Executorとは

Executorは

「仕事を管理する監督」

です。

スレッドを直接作ったり終了したりする面倒な処理を代わりに行ってくれます。

---

# 基本的な使い方

```python
from concurrent.futures import ThreadPoolExecutor

def work(name):
    print(f"{name} 開始")
    print(f"{name} 終了")

with ThreadPoolExecutor(max_workers=3) as executor:
    executor.submit(work, "A")
    executor.submit(work, "B")
    executor.submit(work, "C")
```

---

# submit()

仕事を登録します。

```python
future = executor.submit(work, "Motor1")
```

戻り値は Future オブジェクトです。

---

# Futureとは

Futureは

「未来の結果」

を表すオブジェクトです。

```python
result = future.result()
```

で終了を待ち、戻り値を受け取れます。

---

# max_workers

同時に動くスレッド数です。

```python
ThreadPoolExecutor(max_workers=3)
```

PLCでモータが3台なら3にするのが自然です。

---

# with文を使う理由

```python
with ThreadPoolExecutor(max_workers=3) as executor:
    ...
```

withを抜けると自動的に

- 全タスク終了待ち
- スレッド終了

が行われます。

shutdown()を書く必要がありません。

---

# map() と submit()

## submit()

個別に仕事を登録します。

```python
executor.submit(work, "A")
```

柔軟ですが少し記述量が増えます。

## map()

同じ関数をまとめて実行します。

```python
executor.map(work, ["A","B","C"])
```

シンプルですが細かな制御は苦手です。

---

# Lockとは

複数スレッドが同じデータを書き換えると競合します。

```python
from threading import Lock

lock = Lock()

with lock:
    shared_data.append(value)
```

Lockは

「一人ずつ使ってください」

という札のようなものです。

---

# PLCアプリでLockが必要な場面

- 共通リストへの追加
- ログファイル書き込み
- SQLiteアクセス（設計による）
- 共通変数更新

逆にローカル変数だけなら不要です。

---

# PLCモータ受信アプリでの利用例

```
PLC監視

   ↓

受信要求ON

   ↓

ThreadPoolExecutor

 ├─Motor1受信
 ├─Motor2受信
 └─Motor3受信

   ↓

SQLite保存
```

3台同時に要求が来ても効率よく処理できます。

---

# ThreadPoolExecutorが向いている処理

- PLC通信
- ソケット通信
- HTTP通信
- ファイル読み込み
- データベースアクセス
- ログ保存

---

# 向いていない処理

- AI
- 画像処理
- FFT
- 大量数値計算

これらはProcessPoolExecutorが適しています。

---

# 覚えておきたいポイント

- ThreadPoolExecutorはスレッドを使い回す。
- I/O待ちの多い処理に強い。
- CPUを使い切る計算高速化には向かない。
- with文で安全に終了できる。
- 共有データにはLockを検討する。

---

# まとめ

ThreadPoolExecutorは、

「複数の仕事を効率よくさばくためのスレッド管理機能」

です。

PLCや設備監視アプリでは最もよく使われるマルチスレッドの仕組みの一つであり、
シンプルさ・保守性・安全性のバランスに優れています。

まずは

- Thread
- ThreadPoolExecutor
- Future
- submit()
- Lock

この5つを理解すれば、実務で十分活用できるでしょう。
