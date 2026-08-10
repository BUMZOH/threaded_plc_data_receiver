# Pythonオブジェクト指向の基礎
## ― インスタンス、self、インスタンスメソッド、staticmethod、classmethod を理解する ―

---

## 1. はじめに

Pythonでクラスを使ったプログラムを書いていると、次のような記述が頻繁に登場します。

```python
class MotorReceiver:

    def __init__(self, plc_ip_address: str) -> None:
        self.plc_ip_address = plc_ip_address

    def run(self) -> None:
        self._print_startup_message()

    @staticmethod
    def _create_output_directories() -> None:
        ...
```

ここでは、

- `class`
- インスタンス
- `self`
- `__init__()`
- インスタンス変数
- インスタンスメソッド
- `@staticmethod`
- `@classmethod`

など、オブジェクト指向プログラミングの基本的な仕組みが使われています。

特に最初は、

> `staticmethod` はインスタンスを作らなくても呼べるのに、なぜ `self._create_output_directories()` と書けるのか？

あるいは、

> `_print_startup_message()` は `self.plc_ip_address` を使っているが、インスタンスが無いとエラーにならないのか？

といった疑問が出てきます。

これらを理解するには、まず「クラス」と「インスタンス」の関係から整理する必要があります。

---

# 2. オブジェクト指向とは

オブジェクト指向プログラミングでは、

> データと、そのデータを扱う処理をひとまとまりにする

という考え方をします。

例えばPLC通信を管理するプログラムなら、

- PLCのIPアドレス
- 受信中かどうか
- 要求信号の状態
- PLCを監視する処理
- データを受信する処理

などをひとつのクラスにまとめることができます。

```python
class MotorReceiver:
    ...
```

この `MotorReceiver` は、

> モータ電流値受信処理を管理するための設計図

と考えると分かりやすいです。

---

# 3. クラスは「設計図」

次のコードを考えます。

```python
class MotorReceiver:

    def __init__(self, plc_ip_address: str) -> None:
        self.plc_ip_address = plc_ip_address
```

この時点では、まだ実際のPLC受信オブジェクトは存在していません。

`MotorReceiver` はあくまで設計図です。

実際に使用するには、

```python
receiver = MotorReceiver("192.168.8.1")
```

とします。

これによって、

```text
MotorReceiverという設計図
        ↓
インスタンス生成
        ↓
receiverという実体
```

が作られます。

この「クラスから作られた実体」を **インスタンス** と呼びます。

---

# 4. インスタンスとは

例えば次のように書けます。

```python
receiver1 = MotorReceiver("192.168.8.1")
receiver2 = MotorReceiver("192.168.8.2")
```

この場合、

```text
MotorReceiver
    │
    ├── receiver1
    │      PLC IP = 192.168.8.1
    │
    └── receiver2
           PLC IP = 192.168.8.2
```

という関係になります。

`receiver1` と `receiver2` は同じクラスから作られていますが、別々のインスタンスです。

そのため、それぞれ異なるデータを持つことができます。

---

# 5. `__init__()` の役割

インスタンスを生成するとき、

```python
receiver = MotorReceiver("192.168.8.1")
```

Pythonは自動的に `__init__()` を呼び出します。

```python
def __init__(self, plc_ip_address: str) -> None:
    self.plc_ip_address = plc_ip_address
```

そのため、

```python
receiver = MotorReceiver("192.168.8.1")
```

と書いたときには、概念的には次のような処理が行われます。

```text
MotorReceiverインスタンスを作成
        ↓
__init__() を実行
        ↓
plc_ip_address = "192.168.8.1"
        ↓
self.plc_ip_address に保存
        ↓
receiver にインスタンスを代入
```

つまり、

```python
self.plc_ip_address = plc_ip_address
```

によって、インスタンス自身にPLCのIPアドレスが保存されます。

---

# 6. `self` とは何か

Pythonのクラスを理解するうえで、最重要なのが `self` です。

結論からいうと、

> `self` は「そのメソッドを呼び出したインスタンス自身」

です。

例えば、

```python
receiver = MotorReceiver("192.168.8.1")
receiver.run()
```

とした場合、`run()` 内の `self` は `receiver` を指します。

つまり、

```python
def run(self):
    ...
```

の `self` は実質的に、

```text
self = receiver
```

だと考えることができます。

---

# 7. `self.xxx` はインスタンスが持つデータ

例えば、

```python
self.plc_ip_address = plc_ip_address
```

と書くと、

```python
receiver.plc_ip_address
```

というデータがインスタンスの中に保存されます。

したがって、

```python
print(self.plc_ip_address)
```

は、

```python
print(receiver.plc_ip_address)
```

のような意味になります。

---

# 8. インスタンス変数

次のようなものを **インスタンス変数** と呼びます。

```python
self.plc_ip_address
self.request_latched
self.is_receiving
self.state_lock
```

これらは、

> 個々のインスタンスがそれぞれ持つデータ

です。

今回の `MotorReceiver` では、

```python
def __init__(self, plc_ip_address: str) -> None:
    self.plc_ip_address = plc_ip_address

    self.request_latched = {
        config.name: False
        for config in MOTOR_CONFIGS
    }

    self.is_receiving = {
        config.name: False
        for config in MOTOR_CONFIGS
    }

    self.state_lock = threading.Lock()
```

となっています。

つまり、`MotorReceiver` インスタンスは、

```text
MotorReceiverインスタンス
    │
    ├── plc_ip_address
    ├── request_latched
    ├── is_receiving
    └── state_lock
```

という状態を持っています。

---

# 9. インスタンスメソッド

次のようなメソッドは通常の **インスタンスメソッド** です。

```python
def run(self) -> None:
    ...

def _check_request(self, config: MotorConfig) -> None:
    ...

def _receive_and_save(self, config: MotorConfig) -> None:
    ...

def _print_startup_message(self) -> None:
    ...
```

特徴は、

```python
def メソッド名(self, ...):
```

のように、第1引数が `self` になっていることです。

---

# 10. なぜ `self` を自分で渡さなくてよいのか

例えば、

```python
receiver.run()
```

と呼び出します。

しかし、定義は、

```python
def run(self) -> None:
```

です。

「`self` を渡していないのに大丈夫なのか？」と思うかもしれません。

Pythonは、

```python
receiver.run()
```

を概念的に、

```python
MotorReceiver.run(receiver)
```

のように扱います。

つまり、インスタンス経由でメソッドを呼び出すと、

> Pythonがそのインスタンスを自動的に第1引数へ渡してくれる

という仕組みになっています。

したがって、

```python
receiver.run()
```

では、

```text
self = receiver
```

になります。

---

# 11. `_print_startup_message()` はなぜエラーにならないのか

今回のコードでは、

```python
def _print_startup_message(self) -> None:
    print(f"PLC IPアドレス : {self.plc_ip_address}")
```

となっています。

確かに `self.plc_ip_address` を使用しています。

しかし、プログラムではその前に、

```python
def main() -> None:
    receiver = MotorReceiver(PLC_IP_ADDRESS)
```

としています。

ここで既にインスタンスが生成されています。

さらに `MotorReceiver()` を実行した時点で `__init__()` が動き、

```python
self.plc_ip_address = plc_ip_address
```

が実行されています。

したがって処理順序は、

```text
main()
  ↓
MotorReceiver(PLC_IP_ADDRESS)
  ↓
インスタンス生成
  ↓
__init__()
  ↓
self.plc_ip_address 作成
  ↓
receiver にインスタンス代入
  ↓
receiver.run()
  ↓
self._print_startup_message()
  ↓
self.plc_ip_address を参照
```

となります。

つまり、

> `_print_startup_message()` が呼ばれる時点では、インスタンスは既に生成済み

です。

そのためエラーにはなりません。

---

# 12. インスタンスが無い状態で呼ぶとどうなるか

次のコードは正しくありません。

```python
MotorReceiver._print_startup_message()
```

`_print_startup_message()` は、

```python
def _print_startup_message(self):
```

と定義されているため、`self` が必要です。

しかし、

```python
MotorReceiver._print_startup_message()
```

では `self` に渡すインスタンスがありません。

そのため、概ね次のようなエラーになります。

```text
TypeError:
MotorReceiver._print_startup_message()
missing 1 required positional argument: 'self'
```

---

# 13. `@staticmethod` とは

ここからが今回の中心テーマです。

次のコードがあります。

```python
@staticmethod
def _create_output_directories() -> None:
    for config in MOTOR_CONFIGS:
        config.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
```

`@staticmethod` を付けたメソッドを **スタティックメソッド（静的メソッド）** と呼びます。

特徴は、

> インスタンスを必要としない

ことです。

したがって、

```python
MotorReceiver._create_output_directories()
```

と呼び出すことができます。

インスタンス生成は必要ありません。

---

# 14. staticmethodには `self` が渡されない

通常のインスタンスメソッドでは、

```python
receiver.run()
```

とするとPythonが自動的に、

```python
MotorReceiver.run(receiver)
```

のようにインスタンスを渡します。

しかし `staticmethod` では、この自動処理が行われません。

例えば、

```python
class Sample:

    @staticmethod
    def hello() -> None:
        print("Hello")
```

なら、

```python
Sample.hello()
```

でそのまま実行できます。

`self` はありません。

---

# 15. staticmethodから `self` は使えない

例えば、

```python
class Sample:

    @staticmethod
    def hello() -> None:
        print(self.name)
```

と書いた場合、`self` はどこにも定義されていません。

したがって、

```text
NameError: name 'self' is not defined
```

となります。

`staticmethod` にはPythonがインスタンスを渡してくれないからです。

---

# 16. 今回 `_create_output_directories()` が staticmethod でよい理由

今回のメソッドを見てみます。

```python
@staticmethod
def _create_output_directories() -> None:
    for config in MOTOR_CONFIGS:
        config.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
```

この中では、

```python
self.plc_ip_address
self.request_latched
self.is_receiving
self.state_lock
```

などを一切使用していません。

使用しているのは、

```python
MOTOR_CONFIGS
```

というクラス外の設定だけです。

つまり、

> 特定の `MotorReceiver` インスタンスの状態がなくても実行できる

処理です。

そのため `@staticmethod` にするのは自然です。

---

# 17. staticmethodもインスタンス経由で呼べる

ここは少し紛らわしい重要ポイントです。

`staticmethod` は、

```python
MotorReceiver._create_output_directories()
```

と呼べます。

しかし実は、

```python
receiver._create_output_directories()
```

とも呼べます。

どちらも有効です。

ただし、

```python
receiver._create_output_directories()
```

と書いても、

> `receiver` が `self` として渡されるわけではない

という点が重要です。

`staticmethod` なので、インスタンスは無視されます。

---

# 18. 今回の `run()` を詳しく見る

今回のコードには、

```python
def run(self) -> None:
    self._create_output_directories()
    self._print_startup_message()
```

があります。

見た目は同じですが、内部的な意味は異なります。

## `_create_output_directories()`

```python
self._create_output_directories()
```

これは `staticmethod` です。

したがって、

```text
selfを経由して呼んでいる
        ↓
しかしselfはメソッドに渡されない
        ↓
インスタンス状態は使用しない
```

となります。

## `_print_startup_message()`

```python
self._print_startup_message()
```

こちらは通常のインスタンスメソッドです。

したがって、

```text
selfを経由して呼ぶ
        ↓
selfが自動的にメソッドへ渡される
        ↓
self.plc_ip_address が使用できる
```

となります。

---

# 19. staticmethodをクラス名から呼ぶか、selfから呼ぶか

どちらも可能です。

```python
self._create_output_directories()
```

または、

```python
MotorReceiver._create_output_directories()
```

です。

### `self` から呼ぶ場合

```python
self._create_output_directories()
```

メリットは、

> `MotorReceiver` の処理の流れの一部

として自然に読めることです。

例えば、

```python
def run(self):
    self._create_output_directories()
    self._print_startup_message()
```

と並んでいると、

```text
出力フォルダを作成
    ↓
起動メッセージを表示
    ↓
監視開始
```

という流れが読みやすくなります。

### クラス名から呼ぶ場合

```python
MotorReceiver._create_output_directories()
```

とすると、

> この処理はインスタンスに依存していない

ことがコード上でより明確になります。

どちらを使うかは設計方針によります。

---

# 20. staticmethodに向いている処理

例えば、

```python
class Calculator:

    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b
```

この処理では、

```python
self.xxx
```

を使いません。

したがって、

```python
Calculator.add(10, 20)
```

と呼び出せます。

このような、

> クラスに関連する処理ではあるが、インスタンスの状態は必要ない

処理が `staticmethod` に向いています。

---

# 21. では全部staticmethodにすればよいのか

そうではありません。

例えば、

```python
def save_csv(
    config: MotorConfig,
    values: list[int],
) -> Path:
```

も `self` を使っていません。

技術的には、

```python
class MotorReceiver:

    @staticmethod
    def save_csv(...):
        ...
```

とすることもできます。

しかし現在はクラス外の普通の関数になっています。

これは、

> CSV保存処理は `MotorReceiver` インスタンス固有の処理ではない

と判断して独立関数にしている設計です。

これも非常に自然です。

---

# 22. 普通の関数とstaticmethodの判断

実用上、次のように考えると分かりやすいです。

```text
selfを使う？
    │
    ├── YES
    │     ↓
    │   インスタンスメソッド
    │
    └── NO
          ↓
       その処理はクラスに
       強く関連している？
          │
          ├── YES
          │     ↓
          │   @staticmethod
          │
          └── NO
                ↓
             普通の関数
```

---

# 23. `@classmethod` とは

Pythonにはもう一つ、

```python
@classmethod
```

があります。

例えば、

```python
class Sample:

    @classmethod
    def hello(cls) -> None:
        print(cls)
```

とします。

`classmethod` の第1引数には、

```python
cls
```

を使うのが一般的です。

`cls` は、

> インスタンスではなく「クラスそのもの」

を表します。

---

# 24. selfとclsの違い

```python
self
```

は、

> インスタンス自身

です。

一方、

```python
cls
```

は、

> クラス自身

です。

例えば、

```python
class Sample:

    @classmethod
    def show_class(cls):
        print(cls)
```

を、

```python
Sample.show_class()
```

と呼ぶと、

```text
<class '__main__.Sample'>
```

のようになります。

---

# 25. classmethodの代表的な用途

`classmethod` は、別の方法でインスタンスを生成する「代替コンストラクタ」によく使われます。

例えば、

```python
class MotorReceiver:

    def __init__(self, plc_ip_address: str):
        self.plc_ip_address = plc_ip_address

    @classmethod
    def create_default(cls):
        return cls("192.168.8.1")
```

とすると、

```python
receiver = MotorReceiver.create_default()
```

でインスタンスを生成できます。

この場合、

```python
cls("192.168.8.1")
```

は実質的に、

```python
MotorReceiver("192.168.8.1")
```

です。

---

# 26. 3種類のメソッドを比較する

Pythonのクラスでは、主に次の3種類があります。

| 種類 | 第1引数 | インスタンス情報 | クラス情報 | インスタンスなしで呼べる |
|---|---|---:|---:|---:|
| インスタンスメソッド | `self` | ○ | ○ | 原則× |
| `@classmethod` | `cls` | × | ○ | ○ |
| `@staticmethod` | なし | × | 直接は使わない | ○ |

最初は次のように覚えると十分です。

```text
self.xxx を使う
    ↓
インスタンスメソッド

クラス自体を使う
    ↓
@classmethod

selfもclsも不要
    ↓
@staticmethod候補
```

---

# 27. MotorReceiverを分類する

今回の `MotorReceiver` を分類すると次のようになります。

## インスタンスメソッド

```python
def run(self)
```

`self._check_request()` などを呼び出すため、インスタンスメソッドです。

```python
def _check_request(self, config)
```

以下を使用します。

```python
self.plc_ip_address
self.state_lock
self.request_latched
self.is_receiving
```

明確なインスタンスメソッドです。

```python
def _receive_and_save(self, config)
```

以下を使用します。

```python
self.plc_ip_address
self.state_lock
self.is_receiving
```

これもインスタンスメソッドです。

```python
def _print_startup_message(self)
```

以下を使用します。

```python
self.plc_ip_address
```

したがってインスタンスメソッドです。

## staticmethod

```python
@staticmethod
def _create_output_directories()
```

`self.xxx` を一切使用していないため、`staticmethod` にできます。

---

# 28. 今回のクラス構造を図で見る

```text
MotorReceiver クラス
│
├── インスタンス変数
│   │
│   ├── self.plc_ip_address
│   ├── self.request_latched
│   ├── self.is_receiving
│   └── self.state_lock
│
├── インスタンスメソッド
│   │
│   ├── run(self)
│   ├── _check_request(self, config)
│   ├── _receive_and_save(self, config)
│   └── _print_startup_message(self)
│
└── staticmethod
    │
    └── _create_output_directories()
```

さらにクラス外には、

```text
普通の関数
│
├── save_csv()
└── current_time()
```

があります。

非常に整理された構成です。

---

# 29. なぜ `run()` はselfが必要なのか

一見すると、

```python
def run(self):
```

の中で直接、

```python
self.plc_ip_address
```

を書いていないようにも見えます。

しかし、

```python
self._check_request(config)
```

を呼び出しています。

その `_check_request()` が、

```python
self.plc_ip_address
self.state_lock
```

などを使っています。

したがって `run()` も、

> `MotorReceiver` インスタンスの動作を開始するメソッド

としてインスタンスメソッドにするのが自然です。

---

# 30. オブジェクト指向で重要な「状態」と「処理」

今回のクラスを理解すると、オブジェクト指向の重要な考え方が見えてきます。

`MotorReceiver` は、

```text
状態（データ）
+
処理（メソッド）
```

をひとつにまとめています。

状態：

```python
self.plc_ip_address
self.request_latched
self.is_receiving
self.state_lock
```

処理：

```python
run()
_check_request()
_receive_and_save()
_print_startup_message()
```

これによって、

> PLC受信処理に関する情報をMotorReceiverの中にまとめて管理できる

ようになります。

これがオブジェクト指向の大きなメリットです。

---

# 31. もしクラスを使わなかったら

クラスを使わずに実装すると、

```python
plc_ip_address = ...
request_latched = ...
is_receiving = ...
state_lock = ...
```

といった変数を、複数の関数から共有する必要があります。

すると、

```text
どの変数がどの処理のためのものなのか
```

が分かりにくくなりやすくなります。

クラスを使えば、

```python
receiver.plc_ip_address
receiver.request_latched
receiver.is_receiving
```

のように、

> MotorReceiverが持っている状態

であることが明確になります。

---

# 32. private風メソッドの `_`

今回のメソッド名には、

```python
_check_request
_receive_and_save
_create_output_directories
_print_startup_message
```

のように先頭に `_` が付いています。

Pythonではこれは、

> クラス内部で使うことを意図したメソッド

という慣習です。

例えば、

```python
receiver.run()
```

は外部から使用する公開メソッドですが、

```python
receiver._check_request(...)
```

は通常、外部から直接呼ばないという設計です。

Pythonでは完全なprivateではありませんが、

```text
_ が付いている
    ↓
内部処理なので通常は外部から直接使わない
```

と覚えておくとよいです。

---

# 33. staticmethodだから高速になるわけではない

`staticmethod` は、

> 高速化のための機能

ではありません。

主な目的は、

> このメソッドはインスタンス状態を必要としない

という設計上の意味をコードで表現することです。

したがって、

```python
@staticmethod
```

を付ける最大のメリットは、可読性と設計意図の明確化です。

---

# 34. staticmethodを使う判断基準

実際のプログラミングでは、まず次の質問をします。

### 質問1

そのメソッドで、

```python
self.xxx
```

を使うか？

使うなら通常のインスタンスメソッドです。

### 質問2

`self` は使わないが、そのクラスに置く意味が強いか？

強いなら `staticmethod` 候補です。

### 質問3

クラスとは独立した処理か？

独立しているなら普通の関数にする方が自然です。

---

# 35. 今回の例で判断する

## `_print_startup_message()`

```python
print(self.plc_ip_address)
```

を使用。

したがって、

```text
インスタンスメソッド
```

です。

## `_create_output_directories()`

```python
self.xxx
```

を使用しません。

しかし、

> MotorReceiver起動準備の処理

としてクラスに属させる意味があります。

したがって、

```text
staticmethod
```

が自然です。

## `save_csv()`

`self` は使いません。

さらに、

> CSVへ保存する独立した処理

と考えられます。

したがって、

```text
普通の関数
```

としてクラス外に置く設計も自然です。

---

# 36. よくある誤解

## 誤解1：staticmethodはインスタンスから呼べない

違います。

```python
MotorReceiver._create_output_directories()
```

でも、

```python
receiver._create_output_directories()
```

でも呼べます。

重要なのは、

> 呼び出したインスタンスが `self` として渡されない

ということです。

---

## 誤解2：selfはPythonの予約語

厳密には `self` はPythonの予約語ではありません。

例えば理論上は、

```python
def hello(x):
    print(x)
```

としても動作します。

しかしPythonでは、

```python
def hello(self):
```

と書くのが圧倒的に一般的な慣習です。

したがって、通常は必ず `self` を使います。

---

## 誤解3：staticmethodは必ず使わなければならない

そうではありません。

クラス外の普通の関数として実装してもよい場合があります。

`staticmethod` は、

> クラスとの関連性をコード上で表現したい

場合に使用します。

---

# 37. 最小サンプル

次のコードを実際に試すと理解しやすいです。

```python
class Sample:

    def __init__(self, name: str) -> None:
        self.name = name

    def instance_method(self) -> None:
        print("インスタンスメソッド")
        print(f"name = {self.name}")
        print(f"self = {self}")

    @staticmethod
    def static_method() -> None:
        print("staticmethod")
```

使用：

```python
sample = Sample("motor1")

sample.instance_method()
sample.static_method()

Sample.static_method()
```

これはすべて正常に動作します。

しかし、

```python
Sample.instance_method()
```

はエラーになります。

`instance_method()` に必要な `self` が存在しないからです。

---

# 38. 呼び出し方を内部動作で比較する

通常のインスタンスメソッド：

```python
sample.instance_method()
```

概念的には、

```python
Sample.instance_method(sample)
```

です。

一方 `staticmethod`：

```python
sample.static_method()
```

は、

```python
Sample.static_method()
```

とほぼ同じです。

`sample` は自動的には渡されません。

---

# 39. MotorReceiverの実行順序

今回のプログラム全体を見ると、次のような流れになります。

```text
if __name__ == "__main__":
        │
        ↓
      main()
        │
        ↓
MotorReceiver(PLC_IP_ADDRESS)
        │
        ↓
    __init__()
        │
        ├── self.plc_ip_address
        ├── self.request_latched
        ├── self.is_receiving
        └── self.state_lock
        │
        ↓
receiver にインスタンス代入
        │
        ↓
receiver.run()
        │
        ├── _create_output_directories()
        │       ↑
        │       staticmethod
        │
        ├── _print_startup_message()
        │       ↑
        │       インスタンスメソッド
        │
        └── while True
                │
                ↓
        _check_request()
                │
                ↓
        必要ならThread生成
                │
                ↓
        _receive_and_save()
```

この流れを見ると、

> `self` を使用するメソッドが呼ばれる前に、既にインスタンス生成と `__init__()` が完了している

ことがよく分かります。

---

# 40. オブジェクト指向を学ぶうえでの重要ポイント

今回の内容から、まず次の5点をしっかり押さえておけば十分です。

1. **クラスは設計図**
2. **インスタンスはクラスから作った実体**
3. **selfはそのインスタンス自身**
4. **self.xxxはインスタンス固有の状態**
5. **staticmethodはインスタンス状態を必要としないメソッド**

さらに慣れてきたら、

- classmethod
- 継承
- カプセル化
- ポリモーフィズム
- 抽象クラス

などへ進むと理解しやすくなります。

---

# 41. 実践的な判断フロー

メソッドを作るときは、次の順番で考えると便利です。

```text
この処理はインスタンス固有のデータを使う？
        │
        ├── YES
        │     ↓
        │   def method(self):
        │
        └── NO
              ↓
      クラスそのものを使う？
              │
              ├── YES
              │     ↓
              │   @classmethod
              │   def method(cls):
              │
              └── NO
                    ↓
            クラスに属する意味がある？
                    │
                    ├── YES
                    │     ↓
                    │   @staticmethod
                    │
                    └── NO
                          ↓
                       普通の関数
```

これは非常に実用的な判断基準です。

---

# 42. 今回のコードでの最終整理

今回の `MotorReceiver` では、

```python
def _print_startup_message(self)
```

は、

```python
self.plc_ip_address
```

を使用するためインスタンスメソッドです。

一方、

```python
@staticmethod
def _create_output_directories()
```

はインスタンスの情報を一切必要としません。

そのため `staticmethod` にできます。

そして、

```python
self._create_output_directories()
```

とインスタンス経由で呼んでいても、

> `staticmethod` に `self` が渡されているわけではありません。

これが今回の最も重要なポイントです。

---

# 43. まとめ

Pythonのオブジェクト指向では、

```text
クラス
    ↓
インスタンス生成
    ↓
__init__()
    ↓
self.xxx に状態を保存
    ↓
インスタンスメソッドから利用
```

という流れが基本です。

通常のメソッドは、

```python
def method(self):
```

とし、インスタンス固有の状態を扱います。

`staticmethod` は、

```python
@staticmethod
def method():
```

とし、

> インスタンス固有の状態を必要としないが、そのクラスに関連する処理

に使用します。

`classmethod` は、

```python
@classmethod
def method(cls):
```

とし、

> インスタンスではなくクラスそのものを扱う処理

に使用します。

今回のコードを理解するためには、特に、

```text
self = インスタンス自身
```

という感覚を身につけることが最重要です。

これが分かると、

- `__init__()`
- インスタンス変数
- インスタンスメソッド
- staticmethod
- classmethod

の関係が一気につながって見えるようになります。

---

# 44. 覚え方

最後に、短く覚えるなら次の形がおすすめです。

```text
selfを使う
    → インスタンスメソッド

clsを使う
    → classmethod

selfもclsも使わない
    → staticmethod候補

クラスに置く必要もない
    → 普通の関数
```

そして、

```text
self は「そのオブジェクト自身」
```

これをオブジェクト指向の最初の軸として覚えておくと、今後のPythonクラス設計がかなり理解しやすくなります。
